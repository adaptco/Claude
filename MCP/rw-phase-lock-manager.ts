import type { LockHandle, LockMode, AgentId } from "@agent-mesh/core";
import { randomUUID } from "crypto";

interface LockEntry {
  handle: LockHandle;
  mode: LockMode;
  timer: ReturnType<typeof setTimeout>;
}

interface WaitEntry {
  mode: LockMode;
  holder: AgentId;
  resolve: (h: LockHandle) => void;
  reject: (e: Error) => void;
}

/**
 * In-process RW Phase Lock Manager.
 *
 * Invariants:
 *  - Multiple concurrent READ locks are allowed on the same resource.
 *  - A WRITE lock is exclusive: no reads or other writes while held.
 *  - Waiters are queued in FIFO order; write-preference is applied
 *    (a pending write blocks new reads from jumping the queue).
 *  - Each lock has a TTL; expired locks are force-released and fossiled
 *    via the provided onExpiry callback.
 */
export class InProcRWPhaseLockManager {
  private readonly active = new Map<string, Set<LockEntry>>();
  private readonly waiters = new Map<string, WaitEntry[]>();
  private readonly DEFAULT_TTL_MS = 30_000;

  constructor(
    private readonly onExpiry?: (
      lockId: string,
      resourceId: string,
      holder: AgentId,
      mode: LockMode
    ) => void
  ) {}

  async acquire(
    resourceId: string,
    mode: LockMode,
    holder: AgentId,
    ttlMs = this.DEFAULT_TTL_MS
  ): Promise<LockHandle> {
    return new Promise((resolve, reject) => {
      this.tryAcquire(resourceId, mode, holder, ttlMs, resolve, reject);
    });
  }

  private tryAcquire(
    resourceId: string,
    mode: LockMode,
    holder: AgentId,
    ttlMs: number,
    resolve: (h: LockHandle) => void,
    reject: (e: Error) => void
  ) {
    const active = this.active.get(resourceId) ?? new Set();
    const waiters = this.waiters.get(resourceId) ?? [];

    const canAcquire =
      mode === "read"
        ? // Reads blocked if any active write OR pending write (write-preference)
          ![...active].some((e) => e.mode === "write") &&
          !waiters.some((w) => w.mode === "write")
        : // Writes blocked if anything active
          active.size === 0;

    if (canAcquire) {
      const lockId = randomUUID();
      const now = Date.now();
      const handle: LockHandle = {
        lockId,
        resourceId,
        mode,
        holder,
        acquiredAt: now,
        expiresAt: now + ttlMs,
        release: () => this.release(resourceId, lockId),
      };

      const timer = setTimeout(() => {
        if (this.forceRelease(resourceId, lockId)) {
          this.onExpiry?.(lockId, resourceId, holder, mode);
          this.drain(resourceId);
        }
      }, ttlMs);

      const entry: LockEntry = { handle, mode, timer };
      active.add(entry);
      this.active.set(resourceId, active);
      resolve(handle);
    } else {
      // Enqueue
      const queue = this.waiters.get(resourceId) ?? [];
      queue.push({ mode, holder, resolve, reject });
      this.waiters.set(resourceId, queue);
    }
  }

  private async release(resourceId: string, lockId: string): Promise<void> {
    this.forceRelease(resourceId, lockId);
    this.drain(resourceId);
  }

  private forceRelease(resourceId: string, lockId: string): boolean {
    const active = this.active.get(resourceId);
    if (!active) return false;
    for (const entry of active) {
      if (entry.handle.lockId === lockId) {
        clearTimeout(entry.timer);
        active.delete(entry);
        if (active.size === 0) this.active.delete(resourceId);
        return true;
      }
    }
    return false;
  }

  /** Drain the waiter queue after a release */
  private drain(resourceId: string) {
    const waiters = this.waiters.get(resourceId);
    if (!waiters || waiters.length === 0) return;

    const active = this.active.get(resourceId) ?? new Set();

    // Try to unblock as many compatible waiters as possible
    let i = 0;
    while (i < waiters.length) {
      const w = waiters[i];
      const canGrant =
        w.mode === "read"
          ? ![...active].some((e) => e.mode === "write")
          : active.size === 0;

      if (canGrant) {
        waiters.splice(i, 1);
        const lockId = randomUUID();
        const now = Date.now();
        const ttlMs = this.DEFAULT_TTL_MS;
        const handle: LockHandle = {
          lockId,
          resourceId,
          mode: w.mode,
          holder: w.holder,
          acquiredAt: now,
          expiresAt: now + ttlMs,
          release: () => this.release(resourceId, lockId),
        };
        const timer = setTimeout(() => {
          if (this.forceRelease(resourceId, lockId)) {
            this.onExpiry?.(lockId, resourceId, w.holder, w.mode);
            this.drain(resourceId);
          }
        }, ttlMs);
        active.add({ handle, mode: w.mode, timer });
        this.active.set(resourceId, active);
        w.resolve(handle);

        // If we just granted a write, stop — writes are exclusive
        if (w.mode === "write") break;
      } else {
        i++;
      }
    }

    if (waiters.length === 0) this.waiters.delete(resourceId);
    else this.waiters.set(resourceId, waiters);
  }

  /** Snapshot of current lock state (for debugging/UI) */
  snapshot(): Record<string, { mode: LockMode; holder: AgentId }[]> {
    const out: Record<string, { mode: LockMode; holder: AgentId }[]> = {};
    for (const [res, entries] of this.active) {
      out[res] = [...entries].map((e) => ({
        mode: e.mode,
        holder: e.handle.holder,
      }));
    }
    return out;
  }
}
