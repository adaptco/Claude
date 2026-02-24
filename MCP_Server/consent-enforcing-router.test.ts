import { describe, it, expect, vi, beforeEach } from "vitest";
import { ConsentEnforcingRouter } from "./consent-enforcing-router.js";
import { InMemoryArtifactStore } from "../../artifact-store/src/in-memory-store.js";
import type {
  Agent,
  AgentId,
  AgentMessage,
  AgentRole,
  ConsentDecision,
  ConsentRequest,
  LLMAdapter,
  Tool,
} from "../../core/src/types.js";
import { StubLLMAdapter } from "../../adapters/stub/src/stub-adapter.js";
import { randomUUID } from "crypto";

// ─── Minimal concrete Agent for testing ──────────────────────────────────────
function makeAgent(
  id: AgentId,
  consentDecision: ConsentDecision = "granted",
  role: AgentRole = "specialist"
): Agent & { calls: AgentMessage[] } {
  const adapter = new StubLLMAdapter(id);
  const calls: AgentMessage[] = [];
  return {
    agentId: id,
    role,
    llm: adapter as unknown as LLMAdapter,
    tools: [] as Tool[],
    calls,
    async handleMessage(msg: AgentMessage): Promise<AgentMessage> {
      calls.push(msg);
      return {
        id: randomUUID(),
        from: id,
        to: msg.from,
        type: "result",
        payload: { ack: true },
        context: { taskTreeId: msg.context.taskTreeId },
        timestamp: Date.now(),
      };
    },
    async requestConsent(_req: ConsentRequest): Promise<ConsentDecision> {
      return consentDecision;
    },
    async capabilityVector(): Promise<number[]> {
      return adapter.embeddings(id);
    },
  };
}

function makeMsg(
  to: AgentId,
  type: AgentMessage["type"] = "task",
  taskTreeId = "tree-1"
): AgentMessage {
  return {
    id: randomUUID(),
    from: "gateway",
    to,
    type,
    payload: { task: "do something" },
    context: { taskTreeId },
    timestamp: Date.now(),
  };
}

// ─── Tests ────────────────────────────────────────────────────────────────────
describe("ConsentEnforcingRouter", () => {
  let store: InMemoryArtifactStore;
  let router: ConsentEnforcingRouter;

  beforeEach(() => {
    store = new InMemoryArtifactStore();
    router = new ConsentEnforcingRouter(store, {
      requireExplicitConsent: false,
      consentCacheTtlMs: 60_000,
    });
  });

  // ── 1. Happy path routing ─────────────────────────────────────────────────
  describe("permissive mode (requireExplicitConsent: false)", () => {
    it("routes a task message to the target agent's handleMessage", async () => {
      const agent = makeAgent("specialist-1");
      router.register(agent);

      const msg = makeMsg("specialist-1");
      const reply = await router.route(msg);

      expect(agent.calls).toHaveLength(1);
      expect(agent.calls[0].id).toBe(msg.id);
      expect(reply.type).toBe("result");
      expect((reply.payload as { ack: boolean }).ack).toBe(true);
    });

    it("writes a message_routed fossil for every successful route", async () => {
      router.register(makeAgent("spec-A"));
      await router.route(makeMsg("spec-A"));

      const fossils = await store.fossils();
      const routed = fossils.filter((f) => f.event === "message_routed");
      expect(routed).toHaveLength(1);
    });

    it("routes query and artifact message types without errors", async () => {
      const agent = makeAgent("spec-Q");
      router.register(agent);

      await router.route(makeMsg("spec-Q", "query"));
      await router.route(makeMsg("spec-Q", "artifact"));

      expect(agent.calls).toHaveLength(2);
    });
  });

  // ── 2. Consent enforcement ────────────────────────────────────────────────
  describe("explicit consent mode (requireExplicitConsent: true)", () => {
    beforeEach(() => {
      router = new ConsentEnforcingRouter(store, {
        requireExplicitConsent: true,
        consentCacheTtlMs: 60_000,
      });
    });

    it("delivers message when agent grants consent", async () => {
      const agent = makeAgent("grantee", "granted");
      router.register(agent);

      const msg = makeMsg("grantee");
      const reply = await router.route(msg);

      expect(agent.calls).toHaveLength(1);
      expect(reply.type).toBe("result");
    });

    it("refuses delivery and writes refusal fossil when agent denies consent", async () => {
      const agent = makeAgent("denier", "denied");
      router.register(agent);

      const msg = makeMsg("denier");
      const reply = await router.route(msg);

      // handleMessage must NOT have been called
      expect(agent.calls).toHaveLength(0);

      // Reply is an error
      expect(reply.type).toBe("error");
      expect((reply.payload as { reason: string }).reason).toContain("Consent denied");

      // A refusal fossil must exist
      const fossils = await store.fossils();
      const refused = fossils.filter((f) => f.event === "message_refused");
      expect(refused).toHaveLength(1);
    });

    it("caches a granted consent so requestConsent is only called once per action", async () => {
      const spy = vi.fn().mockResolvedValue("granted" as ConsentDecision);
      const agent = makeAgent("cached-agent", "granted");
      (agent as unknown as { requestConsent: typeof spy }).requestConsent = spy;
      router.register(agent);

      await router.route(makeMsg("cached-agent"));
      await router.route(makeMsg("cached-agent")); // same from+to+action → cache hit

      expect(spy).toHaveBeenCalledTimes(1);
    });

    it("fossils consent_granted event when consent is granted", async () => {
      router.register(makeAgent("fossil-grant", "granted"));
      await router.route(makeMsg("fossil-grant"));

      const fossils = await store.fossils();
      const granted = fossils.filter((f) => f.event === "consent_granted");
      expect(granted.length).toBeGreaterThanOrEqual(1);
    });

    it("fossils consent_denied event when consent is denied", async () => {
      router.register(makeAgent("fossil-deny", "denied"));
      await router.route(makeMsg("fossil-deny"));

      const fossils = await store.fossils();
      const denied = fossils.filter((f) => f.event === "consent_denied");
      expect(denied.length).toBeGreaterThanOrEqual(1);
    });
  });

  // ── 3. Unknown target ─────────────────────────────────────────────────────
  describe("unknown target", () => {
    it("returns an error message for unknown agent target", async () => {
      const msg = makeMsg("does-not-exist");
      const reply = await router.route(msg);

      expect(reply.type).toBe("error");
      expect((reply.payload as { reason: string }).reason).toContain("does-not-exist");
    });

    it("writes a message_refused fossil for unknown target", async () => {
      await router.route(makeMsg("ghost-agent"));

      const fossils = await store.fossils();
      const refused = fossils.filter((f) => f.event === "message_refused");
      expect(refused).toHaveLength(1);
    });
  });

  // ── 4. Fossil chain integrity ─────────────────────────────────────────────
  describe("fossil chain integrity", () => {
    it("fossil chain is valid after multiple routes", async () => {
      router.register(makeAgent("chain-agent"));

      for (let i = 0; i < 5; i++) {
        await router.route(makeMsg("chain-agent"));
      }

      const snap = store.snapshot();
      expect(snap.chainValid).toBe(true);
      expect(snap.fossilCount).toBeGreaterThanOrEqual(5);
    });
  });

  // ── 5. Broadcast ─────────────────────────────────────────────────────────
  describe("broadcast", () => {
    it("delivers broadcast to all agents except sender", async () => {
      const agentA = makeAgent("bcast-A");
      const agentB = makeAgent("bcast-B");
      const agentC = makeAgent("bcast-C");
      router.register(agentA);
      router.register(agentB);
      router.register(agentC);

      const msg: AgentMessage = {
        id: randomUUID(),
        from: "bcast-A", // sender
        to: "broadcast",
        type: "task",
        payload: { announce: true },
        context: { taskTreeId: "bc-1" },
        timestamp: Date.now(),
      };

      const replies = await router.broadcast(msg);
      // bcast-B and bcast-C should each receive it; bcast-A should not
      expect(agentA.calls).toHaveLength(0);
      expect(agentB.calls).toHaveLength(1);
      expect(agentC.calls).toHaveLength(1);
      expect(replies).toHaveLength(2);
    });
  });

  // ── 6. Agent throws ───────────────────────────────────────────────────────
  describe("agent error handling", () => {
    it("returns error message if target agent's handleMessage throws", async () => {
      const throwingAgent: Agent = {
        agentId: "thrower",
        role: "specialist",
        llm: new StubLLMAdapter() as unknown as LLMAdapter,
        tools: [],
        async handleMessage(_msg) { throw new Error("agent exploded"); },
        async requestConsent(_req) { return "granted"; },
        async capabilityVector() { return []; },
      };
      router.register(throwingAgent);

      const reply = await router.route(makeMsg("thrower"));
      expect(reply.type).toBe("error");
      expect((reply.payload as { reason: string }).reason).toContain("agent exploded");
    });
  });
});
