"""
Deterministic Merkle Anchoring System
====================================

Threat Model RC6: Anchor window deterministic and recorded

Key guarantees:
- Deterministic window definition (window_start, window_end)
- Snapshot boundary captured (snapshot_max_created_at) to prevent partial windows
- Deterministic leaf ordering (by event id ASC)
- Idempotent anchor submission (anchor_id unique)
- Retroactive insertion prevention (created_at must be > last anchored window_end)

This module is intentionally storage-agnostic except for small SQL snippets and
expects an async DB connection compatible with asyncpg-like methods:
- fetchval(query, *args)
- fetch(query, *args)
- fetchrow(query, *args)
- execute(query, *args)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple


# =============================================================================
# Merkle primitives
# =============================================================================

def _h(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _hash_pair(left_hex: str, right_hex: str) -> str:
    return _h(bytes.fromhex(left_hex) + bytes.fromhex(right_hex))


class MerkleTree:
    """
    Simple SHA-256 Merkle tree over hex leaf hashes.
    Deterministic: duplicates last node when odd count.
    """
    def __init__(self, leaf_hashes_hex: Sequence[str]):
        if not leaf_hashes_hex:
            raise ValueError("MerkleTree requires at least one leaf")
        self.leaves = list(leaf_hashes_hex)
        self.levels: List[List[str]] = []
        self._build()

    def _build(self) -> None:
        level = self.leaves[:]
        self.levels.append(level)
        while len(level) > 1:
            nxt: List[str] = []
            for i in range(0, len(level), 2):
                left = level[i]
                right = level[i + 1] if i + 1 < len(level) else level[i]
                nxt.append(_hash_pair(left, right))
            level = nxt
            self.levels.append(level)

    def root(self) -> str:
        return self.levels[-1][0]


# =============================================================================
# Anchor records
# =============================================================================

class AnchorState(str, Enum):
    BUILDING = "BUILDING"
    SUBMITTED = "SUBMITTED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class AnchorWindow:
    window_id: str
    window_start: datetime
    window_end: datetime
    snapshot_max_created_at: datetime
    event_count: int
    merkle_root: str
    leaf_hashes: List[str]
    created_at: datetime


@dataclass
class AnchorRecord:
    anchor_id: str
    window_id: str
    state: AnchorState
    merkle_root: str
    window_start: datetime
    window_end: datetime
    snapshot_max_created_at: datetime
    event_count: int
    anchor_target: str
    transaction_hash: Optional[str]
    created_at: datetime
    updated_at: datetime


# =============================================================================
# Anchor manager
# =============================================================================

class AnchorManager:
    def __init__(self, *, window_duration: timedelta, anchor_target: str = "polygon"):
        self.window_duration = window_duration
        self.anchor_target = anchor_target

    async def latest_window_end(self, db_conn) -> Optional[datetime]:
        return await db_conn.fetchval("SELECT MAX(window_end) FROM anchor_records")

    async def reject_retro_inserts(self, *, db_conn, event_created_at: datetime) -> None:
        """
        Enforce: after any anchor exists, no event may be inserted with created_at
        <= last anchored window_end.
        """
        last_end = await db_conn.fetchval(
            "SELECT window_end FROM anchor_records ORDER BY window_end DESC LIMIT 1"
        )
        if last_end and event_created_at <= last_end:
            raise ValueError(f"Retroactive insertion rejected: {event_created_at} <= {last_end}")

    async def create_anchor_window(self, *, db_conn, window_start: Optional[datetime] = None) -> AnchorWindow:
        # Determine window bounds deterministically
        if window_start is None:
            last_end = await self.latest_window_end(db_conn)
            # If no anchors exist, default to the most recent completed duration
            window_start = last_end or (datetime.now(timezone.utc) - self.window_duration)

        window_start = _ensure_utc(window_start)
        window_end = window_start + self.window_duration

        # Snapshot boundary: capture max(created_at) within the window BEFORE leaf fetch.
        # This prevents partial windows if events arrive during build.
        snapshot_max_created_at = await db_conn.fetchval(
            """
            SELECT MAX(created_at)
            FROM events
            WHERE created_at >= $1 AND created_at < $2
            """,
            window_start, window_end
        )
        if snapshot_max_created_at is None:
            raise ValueError("No events in window")

        snapshot_max_created_at = _ensure_utc(snapshot_max_created_at)

        # Fetch leaves deterministically by event id ASC, and bounded by snapshot_max_created_at.
        rows = await db_conn.fetch(
            """
            SELECT id, hash_current
            FROM events
            WHERE created_at >= $1
              AND created_at <= $2
            ORDER BY id ASC
            """,
            window_start, snapshot_max_created_at
        )
        leaf_hashes = [r["hash_current"] for r in rows]
        if not leaf_hashes:
            raise ValueError("No events in snapshot window")

        tree = MerkleTree(leaf_hashes)
        merkle_root = tree.root()

        window_id = f"window-{window_start.strftime('%Y%m%d%H%M%S')}-{window_end.strftime('%Y%m%d%H%M%S')}"

        return AnchorWindow(
            window_id=window_id,
            window_start=window_start,
            window_end=window_end,
            snapshot_max_created_at=snapshot_max_created_at,
            event_count=len(leaf_hashes),
            merkle_root=merkle_root,
            leaf_hashes=leaf_hashes,
            created_at=datetime.now(timezone.utc),
        )

    async def submit_anchor(self, *, db_conn, window: AnchorWindow) -> AnchorRecord:
        anchor_id = f"anchor-{window.window_id}"

        existing = await db_conn.fetchrow("SELECT * FROM anchor_records WHERE anchor_id = $1", anchor_id)
        if existing:
            return AnchorRecord(**dict(existing))

        now = datetime.now(timezone.utc)
        record = AnchorRecord(
            anchor_id=anchor_id,
            window_id=window.window_id,
            state=AnchorState.BUILDING,
            merkle_root=window.merkle_root,
            window_start=window.window_start,
            window_end=window.window_end,
            snapshot_max_created_at=window.snapshot_max_created_at,
            event_count=window.event_count,
            anchor_target=self.anchor_target,
            transaction_hash=None,
            created_at=now,
            updated_at=now,
        )

        await db_conn.execute(
            """
            INSERT INTO anchor_records (
              anchor_id, window_id, state, merkle_root,
              window_start, window_end, snapshot_max_created_at, event_count,
              anchor_target, transaction_hash, created_at, updated_at
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
            """,
            record.anchor_id, record.window_id, record.state, record.merkle_root,
            record.window_start, record.window_end, record.snapshot_max_created_at, record.event_count,
            record.anchor_target, record.transaction_hash, record.created_at, record.updated_at
        )

        try:
            # Placeholder external submission. Replace with real chain anchoring.
            tx = f"0x{record.merkle_root[:40]}"

            await db_conn.execute(
                """
                UPDATE anchor_records
                SET state=$1, transaction_hash=$2, updated_at=$3
                WHERE anchor_id=$4
                """,
                AnchorState.SUBMITTED, tx, datetime.now(timezone.utc), anchor_id
            )

            record.state = AnchorState.SUBMITTED
            record.transaction_hash = tx
            record.updated_at = datetime.now(timezone.utc)
            return record

        except Exception:
            await db_conn.execute(
                "UPDATE anchor_records SET state=$1, updated_at=$2 WHERE anchor_id=$3",
                AnchorState.FAILED, datetime.now(timezone.utc), anchor_id
            )
            record.state = AnchorState.FAILED
            record.updated_at = datetime.now(timezone.utc)
            raise


def anchor_records_ddl() -> str:
    """
    Production DDL for anchor_records table (Postgres).
    """
    return """
CREATE TABLE IF NOT EXISTS anchor_records (
  anchor_id TEXT PRIMARY KEY,
  window_id TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('BUILDING','SUBMITTED','FAILED')),
  merkle_root TEXT NOT NULL,
  window_start TIMESTAMPTZ NOT NULL,
  window_end TIMESTAMPTZ NOT NULL,
  snapshot_max_created_at TIMESTAMPTZ NOT NULL,
  event_count BIGINT NOT NULL CHECK (event_count > 0),
  anchor_target TEXT NOT NULL,
  transaction_hash TEXT,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_anchor_window ON anchor_records(window_start, window_end);
CREATE INDEX IF NOT EXISTS idx_anchor_state ON anchor_records(state);
"""


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        # Assume UTC if naive
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
