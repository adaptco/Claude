from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Iterator

import numpy as np

EMBED_DIM = 1536
CHUNK_CHARS = 1600
CHUNK_OVERLAP = 320
INCLUDE_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".md", ".json", ".yaml", ".yml", ".toml", ".txt"}
EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "dist",
    ".turbo",
    "__pycache__",
    ".pytest_cache",
}


def _hash_embed_batch(texts: list[str]) -> np.ndarray:
    out = np.zeros((len(texts), EMBED_DIM), dtype=np.float32)
    for i, text in enumerate(texts):
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        repeat = EMBED_DIM // len(digest) + 1
        buf = digest * repeat
        raw = np.frombuffer(buf[:EMBED_DIM], dtype=np.uint8).astype(np.float32)
        vec = (raw / 255.0) * 2.0 - 1.0
        out[i] = vec
    return out


def _normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return matrix / norms


def embed_batch(texts: list[str]) -> np.ndarray:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if api_key:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=api_key)
            res = client.embeddings.create(model="text-embedding-3-small", input=texts)
            matrix = np.array([item.embedding for item in res.data], dtype=np.float32)
            return _normalize(matrix)
        except Exception:
            pass

    return _normalize(_hash_embed_batch(texts))


def iter_repo_files(repo_root: Path) -> Iterator[Path]:
    for path in sorted(repo_root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
        if path.suffix not in INCLUDE_EXTENSIONS:
            continue
        yield path


def chunk_file(repo_root: Path, path: Path) -> Iterator[tuple[str, str]]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if len(text.strip()) < 16:
        return

    rel = str(path.relative_to(repo_root))
    start = 0
    while start < len(text):
        end = min(start + CHUNK_CHARS, len(text))
        chunk = text[start:end]
        key = f"{rel}:{start}"
        yield key, f"# FILE: {rel}\n{chunk}"
        start += CHUNK_CHARS - CHUNK_OVERLAP


class EmbeddingIndex:
    def __init__(self, repo_root: Path, store_path: Path):
        self.repo_root = repo_root
        self.store_path = store_path
        self.keys: list[str] = []
        self.texts: list[str] = []
        self.matrix: np.ndarray | None = None

    def _load(self) -> bool:
        if not self.store_path.exists():
            return False
        data = np.load(self.store_path, allow_pickle=True)
        self.keys = data["keys"].tolist()
        self.texts = data["texts"].tolist()
        self.matrix = data["vectors"]
        return True

    def build(self) -> None:
        keys: list[str] = []
        texts: list[str] = []

        for path in iter_repo_files(self.repo_root):
            for key, chunk in chunk_file(self.repo_root, path):
                keys.append(key)
                texts.append(chunk)

        if not texts:
            self.keys = []
            self.texts = []
            self.matrix = np.zeros((0, EMBED_DIM), dtype=np.float32)
        else:
            batch_size = 64
            rows: list[np.ndarray] = []
            for i in range(0, len(texts), batch_size):
                rows.append(embed_batch(texts[i : i + batch_size]))
            self.keys = keys
            self.texts = texts
            self.matrix = np.vstack(rows)

        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            self.store_path,
            keys=np.array(self.keys),
            texts=np.array(self.texts),
            vectors=self.matrix,
        )

    def ensure_loaded(self) -> None:
        if self.matrix is not None:
            return
        if not self._load():
            self.build()

    def search(self, query: str, top_k: int = 8, agent_filter: str = "") -> list[dict]:
        self.ensure_loaded()
        assert self.matrix is not None

        if self.matrix.shape[0] == 0:
            return []

        query_vec = embed_batch([query])[0]
        scores = self.matrix @ query_vec

        if agent_filter:
            mask = np.array([agent_filter in key for key in self.keys])
            scores = np.where(mask, scores, -np.inf)

        top_k = max(1, min(top_k, scores.shape[0]))
        idx = np.argpartition(scores, -top_k)[-top_k:]
        idx = idx[np.argsort(scores[idx])[::-1]]

        out: list[dict] = []
        for i in idx:
            score = float(scores[i])
            if score == float("-inf"):
                continue
            out.append(
                {
                    "key": self.keys[i],
                    "file": self.keys[i].split(":", 1)[0],
                    "score": score,
                    "text": self.texts[i][:500],
                }
            )
        return out
