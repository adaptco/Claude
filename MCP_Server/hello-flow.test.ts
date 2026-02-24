/**
 * hello-flow.test.ts
 *
 * End-to-end in-process integration tests for the agent mesh.
 * No network, no API keys, fully deterministic.
 */
import { describe, it, expect, beforeEach } from "vitest";
import { randomUUID } from "crypto";
import { BaseAgent } from "../../../packages/core/src/base-agent.js";
import type {
  AgentMessage,
  ArtifactStore,
  ConsentDecision,
  ConsentRequest,
  LLMAdapter,
} from "../../../packages/core/src/types.js";
import { ConsentEnforcingRouter } from "../../../packages/mcp-router/src/consent-enforcing-router.js";
import { InProcRWPhaseLockManager } from "../../../packages/mcp-router/src/rw-phase-lock-manager.js";
import { InMemoryArtifactStore } from "../../../packages/artifact-store/src/in-memory-store.js";
import { StubLLMAdapter } from "../../../packages/adapters/stub/src/stub-adapter.js";

// ─── Re-usable mini agents (mirrors hello-mesh.ts but test-friendly) ─────────
class OrchestratorAgent extends BaseAgent {
  async handleMessage(msg: AgentMessage): Promise<AgentMessage> {
    const artifact = await this.store.put({
      createdBy: this.agentId,
      taskTreeId: msg.context.taskTreeId,
      content: msg.payload,
    });
    return this.reply(msg, { decomposed: true, artifactId: artifact.id });
  }
}

class SpecialistAgent extends BaseAgent {
  async handleMessage(msg: AgentMessage): Promise<AgentMessage> {
    const result = await this.llm.complete([
      { role: "system", content: "Summarize." },
      { role: "user", content: JSON.stringify(msg.payload) },
    ]);
    const artifact = await this.store.put({
      createdBy: this.agentId,
      taskTreeId: msg.context.taskTreeId,
      content: { summary: result.text },
      embedding: await this.llm.embeddings(result.text),
    });
    const sealed = await this.store.seal(artifact.id, this.agentId);
    return this.reply(msg, { summary: result.text, artifactId: sealed.id });
  }
}

class DenierAgent extends BaseAgent {
  async handleMessage(msg: AgentMessage): Promise<AgentMessage> {
    return this.reply(msg, { shouldNotReach: true }, "error");
  }
}

// ─── Fixture factory ─────────────────────────────────────────────────────────
function buildMesh(requireExplicitConsent = false) {
  const store = new InMemoryArtifactStore();
  const locks = new InProcRWPhaseLockManager();
  const router = new ConsentEnforcingRouter(store, {
    requireExplicitConsent,
    consentCacheTtlMs: 60_000,
  });
  const stub = (id: string) => new StubLLMAdapter(id) as unknown as LLMAdapter;

  const orchestrator = new OrchestratorAgent({
    agentId: "orchestrator",
    role: "orchestrator",
    llm: stub("orch-llm"),
    store,
    systemPrompt: "Orchestrate.",
  });

  const specialist = new SpecialistAgent({
    agentId: "specialist",
    role: "specialist",
    llm: stub("spec-llm"),
    store,
    systemPrompt: "Summarize.",
  });

  const denier = new DenierAgent({
    agentId: "denier",
    role: "gatekeeper",
    llm: stub("denier-llm"),
    store,
    consentPolicy: (): ConsentDecision => "denied",
  });

  router.register(orchestrator);
  router.register(specialist);
  router.register(denier);

  return { store, locks, router, orchestrator, specialist, denier };
}

function taskMsg(to: string, payload: unknown = { task: "summarize stuff" }): AgentMessage {
  return {
    id: randomUUID(),
    from: "gateway",
    to,
    type: "task",
    payload,
    context: { taskTreeId: randomUUID() },
    timestamp: Date.now(),
  };
}

// ─── Tests ────────────────────────────────────────────────────────────────────
describe("hello-flow integration", () => {

  // ── Demo 1: Normal task routing ───────────────────────────────────────────
  describe("Demo 1: normal task flow", () => {
    it("routes task to orchestrator and returns a result", async () => {
      const { router } = buildMesh();
      const reply = await router.route(taskMsg("orchestrator"));
      expect(reply.type).toBe("result");
      expect((reply.payload as { decomposed: boolean }).decomposed).toBe(true);
    });

    it("orchestrator stores a draft artifact", async () => {
      const { store, router } = buildMesh();
      const reply = await router.route(taskMsg("orchestrator"));
      const artifactId = (reply.payload as { artifactId: string }).artifactId;
      const artifact = await store.get(artifactId);
      expect(artifact).not.toBeNull();
      expect(artifact!.status).toBe("draft");
    });

    it("specialist seals an artifact and fossil chain stays valid", async () => {
      const { store, router } = buildMesh();
      const reply = await router.route(taskMsg("specialist"));
      const artifactId = (reply.payload as { artifactId: string }).artifactId;
      const artifact = await store.get(artifactId);

      expect(artifact!.status).toBe("sealed");
      expect(store.verifyChain().valid).toBe(true);
    });

    it("no consent_denied fossil is written on successful route", async () => {
      const { store, router } = buildMesh();
      await router.route(taskMsg("orchestrator"));

      const fossils = await store.fossils();
      const denied = fossils.filter((f) => f.event === "consent_denied");
      expect(denied).toHaveLength(0);
    });

    it("message_routed fossil is written for every successful delivery", async () => {
      const { store, router } = buildMesh();
      await router.route(taskMsg("orchestrator"));
      await router.route(taskMsg("specialist"));

      const fossils = await store.fossils();
      const routed = fossils.filter((f) => f.event === "message_routed");
      expect(routed.length).toBeGreaterThanOrEqual(2);
    });
  });

  // ── Demo 2: RW lock contention ────────────────────────────────────────────
  describe("Demo 2: RW phase lock contention", () => {
    it("two concurrent readers block a writer until they release", async () => {
      const { locks } = buildMesh();
      const res = "shared-doc";

      const [r1, r2] = await Promise.all([
        locks.acquire(res, "read", "reader-A", 5000),
        locks.acquire(res, "read", "reader-B", 5000),
      ]);

      const order: string[] = [];
      const writerPromise = locks.acquire(res, "write", "writer-C", 5000).then(async (w) => {
        order.push("writer-granted");
        await w.release();
      });

      // Give the event loop a tick — writer must NOT be granted yet
      await new Promise((r) => setImmediate(r));
      expect(order).not.toContain("writer-granted");

      order.push("readers-releasing");
      await r1.release();
      await r2.release();
      await writerPromise;

      expect(order).toEqual(["readers-releasing", "writer-granted"]);
    });

    it("writer lock snapshot is empty after release", async () => {
      const { locks } = buildMesh();
      const w = await locks.acquire("lock-cleanup", "write", "W", 5000);
      expect(locks.snapshot()["lock-cleanup"]).toHaveLength(1);
      await w.release();
      expect(locks.snapshot()["lock-cleanup"]).toBeUndefined();
    });

    it("multiple concurrent tasks to specialist don't corrupt artifact store", async () => {
      const { store, router } = buildMesh();

      await Promise.all(
        Array.from({ length: 5 }, (_, i) =>
          router.route(taskMsg("specialist", { task: `task-${i}` }))
        )
      );

      const snap = store.snapshot();
      expect(snap.artifactCount).toBeGreaterThanOrEqual(5);
      expect(snap.chainValid).toBe(true);
    });
  });

  // ── Demo 3: Refusal fossil ────────────────────────────────────────────────
  describe("Demo 3: consent refusal fossil", () => {
    it("routing to unknown agent produces error reply with refusal fossil", async () => {
      const { store, router } = buildMesh();

      const reply = await router.route(taskMsg("nonexistent-agent"));
      expect(reply.type).toBe("error");

      const fossils = await store.fossils();
      const refused = fossils.filter((f) => f.event === "message_refused");
      expect(refused.length).toBeGreaterThanOrEqual(1);
    });

    it("routing to gatekeeper agent (always-deny) produces consent_denied fossil", async () => {
      const { store, router } = buildMesh(/* requireExplicitConsent= */ true);

      const reply = await router.route(taskMsg("denier"));
      expect(reply.type).toBe("error");

      const fossils = await store.fossils();
      const denied = fossils.filter((f) => f.event === "consent_denied");
      expect(denied.length).toBeGreaterThanOrEqual(1);
    });

    it("denier agent's handleMessage is never called when consent is denied", async () => {
      const { router, denier } = buildMesh(true);
      let called = false;
      const origHandle = denier.handleMessage.bind(denier);
      // Wrap to track calls — spy manually since we don't want vi.spyOn complexities
      (denier as unknown as { handleMessage: typeof origHandle }).handleMessage = async (
        msg: AgentMessage
      ) => {
        called = true;
        return origHandle(msg);
      };

      await router.route(taskMsg("denier"));
      expect(called).toBe(false);
    });

    it("refusal fossil payload contains a reason string", async () => {
      const { store, router } = buildMesh();
      await router.route(taskMsg("ghost"));

      const fossils = await store.fossils();
      const refused = fossils.filter((f) => f.event === "message_refused");
      expect(refused.length).toBeGreaterThanOrEqual(1);
      const payload = refused[0].payload as { reason: string };
      expect(typeof payload.reason).toBe("string");
      expect(payload.reason.length).toBeGreaterThan(0);
    });
  });

  // ── Full-run: fossil chain integrity ─────────────────────────────────────
  describe("full scenario chain integrity", () => {
    it("fossil chain is valid after running all three demo scenarios", async () => {
      const { store, locks, router } = buildMesh(true);

      // Demo 1
      await router.route(taskMsg("orchestrator"));
      await router.route(taskMsg("specialist"));

      // Demo 2 (lock interleaving)
      const [r1, r2] = await Promise.all([
        locks.acquire("doc", "read", "A", 5000),
        locks.acquire("doc", "read", "B", 5000),
      ]);
      const wp = locks.acquire("doc", "write", "C", 5000).then((w) => w.release());
      await r1.release();
      await r2.release();
      await wp;

      // Demo 3 (refusal)
      await router.route(taskMsg("ghost"));

      const snap = store.snapshot();
      expect(snap.chainValid).toBe(true);
    });
  });
});
