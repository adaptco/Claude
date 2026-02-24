import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { InProcRWPhaseLockManager } from "./rw-phase-lock-manager.js";

// ─── helpers ──────────────────────────────────────────────────────────────────
const delay = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

describe("InProcRWPhaseLockManager", () => {
  let locks: InProcRWPhaseLockManager;

  beforeEach(() => {
    locks = new InProcRWPhaseLockManager();
  });

  // ── 1. Basic read/write acquire + release ─────────────────────────────────
  describe("basic acquire & release", () => {
    it("grants a single read lock immediately", async () => {
      const h = await locks.acquire("r1", "read", "agent-A");
      expect(h.mode).toBe("read");
      expect(h.holder).toBe("agent-A");
      expect(h.resourceId).toBe("r1");
      await h.release();
    });

    it("grants a single write lock immediately on empty resource", async () => {
      const h = await locks.acquire("w1", "write", "agent-B");
      expect(h.mode).toBe("write");
      await h.release();
    });

    it("snapshot shows active locks", async () => {
      const h = await locks.acquire("snap", "read", "agent-A", 5000);
      const snap = locks.snapshot();
      expect(snap["snap"]).toHaveLength(1);
      expect(snap["snap"][0]).toEqual({ mode: "read", holder: "agent-A" });
      await h.release();
      expect(locks.snapshot()["snap"]).toBeUndefined();
    });
  });

  // ── 2. Multiple concurrent readers ────────────────────────────────────────
  describe("concurrent readers", () => {
    it("allows multiple simultaneous read locks on the same resource", async () => {
      const [h1, h2, h3] = await Promise.all([
        locks.acquire("res", "read", "A"),
        locks.acquire("res", "read", "B"),
        locks.acquire("res", "read", "C"),
      ]);
      const snap = locks.snapshot()["res"];
      expect(snap).toHaveLength(3);
      await h1.release();
      await h2.release();
      await h3.release();
    });

    it("read locks on different resources are independent", async () => {
      const h1 = await locks.acquire("res-a", "read", "A");
      const h2 = await locks.acquire("res-b", "write", "B"); // different resource
      expect(locks.snapshot()["res-a"]).toHaveLength(1);
      expect(locks.snapshot()["res-b"]).toHaveLength(1);
      await h1.release();
      await h2.release();
    });
  });

  // ── 3. Write exclusivity ──────────────────────────────────────────────────
  describe("write exclusivity", () => {
    it("write lock blocks while a read lock is active, then grants after release", async () => {
      const readLock = await locks.acquire("ex", "read", "reader", 5000);

      let writerGranted = false;
      const writerPromise = locks.acquire("ex", "write", "writer", 5000).then((h) => {
        writerGranted = true;
        return h;
      });

      // Writer should not be granted yet
      await delay(20);
      expect(writerGranted).toBe(false);

      await readLock.release();

      const writerHandle = await writerPromise;
      expect(writerGranted).toBe(true);
      expect(writerHandle.mode).toBe("write");
      await writerHandle.release();
    });

    it("second write blocks while first write is held, then grants in order", async () => {
      const w1 = await locks.acquire("seq", "write", "W1", 5000);

      let w2Granted = false;
      const w2Promise = locks.acquire("seq", "write", "W2", 5000).then((h) => {
        w2Granted = true;
        return h;
      });

      await delay(20);
      expect(w2Granted).toBe(false);

      await w1.release();
      const w2 = await w2Promise;
      expect(w2Granted).toBe(true);
      await w2.release();
    });

    it("write-preference blocks new reads that arrive after a pending write", async () => {
      // Acquire a read, then a pending write, then try another read
      const r1 = await locks.acquire("wp", "read", "R1", 5000);

      let writeGranted = false;
      const wPromise = locks.acquire("wp", "write", "W", 5000).then((h) => {
        writeGranted = true;
        return h;
      });

      // This read arrives AFTER the write is queued — should be blocked by write-preference
      let r2Granted = false;
      const r2Promise = locks.acquire("wp", "read", "R2", 5000).then((h) => {
        r2Granted = true;
        return h;
      });

      await delay(20);
      expect(writeGranted).toBe(false);
      expect(r2Granted).toBe(false);

      await r1.release();

      // Write should go first
      const w = await wPromise;
      expect(writeGranted).toBe(true);
      expect(r2Granted).toBe(false); // still waiting

      await w.release();

      // Now R2 gets its turn
      const r2 = await r2Promise;
      expect(r2Granted).toBe(true);
      await r2.release();
    });
  });

  // ── 4. Release idempotency ────────────────────────────────────────────────
  describe("release idempotency", () => {
    it("releasing a lock twice does not throw", async () => {
      const h = await locks.acquire("idem", "read", "A");
      await h.release();
      await expect(h.release()).resolves.toBeUndefined();
    });

    it("snapshot is clean after double-release", async () => {
      const h = await locks.acquire("idem2", "write", "A");
      await h.release();
      await h.release();
      expect(locks.snapshot()["idem2"]).toBeUndefined();
    });
  });

  // ── 5. TTL expiry ─────────────────────────────────────────────────────────
  describe("TTL expiry", () => {
    it("expired lock allows a new acquirer on the same resource", async () => {
      const expired: string[] = [];
      const mgr = new InProcRWPhaseLockManager((lockId) => expired.push(lockId));

      // Acquire with 80ms TTL
      await mgr.acquire("ttl-res", "write", "holder-A", 80);

      // After TTL, a second acquirer should succeed
      await delay(120);
      const h2 = await mgr.acquire("ttl-res", "write", "holder-B", 5000);
      expect(h2.holder).toBe("holder-B");
      expect(expired).toHaveLength(1);
      await h2.release();
    }, 1000);

    it("onExpiry callback fires with correct metadata", async () => {
      const calls: Array<{ lockId: string; resourceId: string; holder: string; mode: string }> = [];
      const mgr = new InProcRWPhaseLockManager((lockId, resourceId, holder, mode) => {
        calls.push({ lockId, resourceId, holder, mode });
      });

      await mgr.acquire("exp-meta", "read", "expiring-agent", 60);
      await delay(100);

      expect(calls).toHaveLength(1);
      expect(calls[0].resourceId).toBe("exp-meta");
      expect(calls[0].holder).toBe("expiring-agent");
      expect(calls[0].mode).toBe("read");
    }, 1000);

    it("waiter that was queued behind an expired lock gets granted", async () => {
      const mgr = new InProcRWPhaseLockManager();

      // Write lock with very short TTL
      const w1 = await mgr.acquire("exp-drain", "write", "W1", 80);

      // Queue a second writer — it should get unblocked by the expiry drain
      let w2Granted = false;
      const w2Promise = mgr.acquire("exp-drain", "write", "W2", 5000).then((h) => {
        w2Granted = true;
        return h;
      });

      // Don't manually release w1 — let it expire
      await delay(150);
      expect(w2Granted).toBe(true);
      const w2 = await w2Promise;
      await w2.release();
      void w1; // suppress unused warning — it expired
    }, 1000);
  });

  // ── 6. Drain ordering (FIFO) ──────────────────────────────────────────────
  describe("FIFO drain ordering", () => {
    it("multiple queued readers are all granted when writer releases", async () => {
      const w = await locks.acquire("fifo", "write", "W", 5000);

      const granted: string[] = [];
      const readers = await Promise.all(
        ["R1", "R2", "R3"].map((id) =>
          locks.acquire("fifo", "read", id, 5000).then((h) => {
            granted.push(id);
            return h;
          })
        )
      );

      await delay(20);
      expect(granted).toHaveLength(0); // all blocked

      await w.release();
      await delay(20);

      expect(granted).toHaveLength(3); // all unblocked simultaneously
      for (const h of readers) await h.release();
    });
  });
});
