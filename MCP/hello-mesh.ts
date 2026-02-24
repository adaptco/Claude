/**
 * hello-mesh.ts
 *
 * Runnable demo: pnpm --filter @agent-mesh/gateway hello
 *
 * What this does:
 *  1. Spins up an InMemoryArtifactStore
 *  2. Creates a ConsentEnforcingRouter
 *  3. Registers two agents:
 *       - OrchestratorAgent  (decomposes tasks, routes sub-tasks)
 *       - SpecialistAgent    (handles "summarize" tasks)
 *  4. Sends a task message through the router
 *  5. Router enforces consent, fossils every event
 *  6. Prints the result + full fossil chain
 *
 * No API keys. No network. Fully in-process.
 */

import { randomUUID } from "crypto";
import { BaseAgent }               from "@agent-mesh/core";
import type {
  AgentMessage,
  ArtifactStore,
  ConsentRequest,
  ConsentDecision,
} from "@agent-mesh/core";
import { ConsentEnforcingRouter }   from "@agent-mesh/mcp-router";
import { InProcRWPhaseLockManager } from "@agent-mesh/mcp-router";
import { InMemoryArtifactStore }    from "@agent-mesh/artifact-store";
import { StubLLMAdapter }           from "@agent-mesh/adapter-stub";

// ─── Colour helpers (no deps) ─────────────────────────────────────────────────
const C = {
  reset:  "\x1b[0m",
  bold:   "\x1b[1m",
  dim:    "\x1b[2m",
  cyan:   "\x1b[36m",
  green:  "\x1b[32m",
  yellow: "\x1b[33m",
  red:    "\x1b[31m",
  blue:   "\x1b[34m",
  magenta:"\x1b[35m",
};

function log(prefix: string, color: string, ...args: unknown[]) {
  console.log(`${color}${C.bold}[${prefix}]${C.reset}`, ...args);
}

// ─── OrchestratorAgent ────────────────────────────────────────────────────────
class OrchestratorAgent extends BaseAgent {
  constructor(store: ArtifactStore) {
    super({
      agentId: "orchestrator",
      role:    "orchestrator",
      llm:     new StubLLMAdapter("orchestrator-llm", "[ORCH]"),
      store,
      systemPrompt: "You orchestrate tasks by decomposing them and routing to specialists.",
    });
  }

  async handleMessage(msg: AgentMessage): Promise<AgentMessage> {
    log("ORCH", C.cyan, `Received ${msg.type} from ${msg.from}:`, JSON.stringify(msg.payload));

    // Decompose: forward the task payload to the specialist
    const subtask: AgentMessage = {
      id:        randomUUID(),
      from:      this.agentId,
      to:        "specialist",
      type:      "task",
      payload:   { instruction: "summarize", input: msg.payload },
      context:   { taskTreeId: msg.context.taskTreeId },
      timestamp: Date.now(),
    };

    // Store a draft artifact for the subtask
    const artifact = await this.store.put({
      createdBy:   this.agentId,
      taskTreeId:  msg.context.taskTreeId,
      content:     subtask.payload,
    });

    log("ORCH", C.cyan, `Created draft artifact ${artifact.id}`);

    return this.reply(msg, {
      status:      "decomposed",
      subtaskId:   subtask.id,
      artifactId:  artifact.id,
      note:        "Subtask created; specialist will handle.",
    });
  }
}

// ─── SpecialistAgent ──────────────────────────────────────────────────────────
class SpecialistAgent extends BaseAgent {
  constructor(store: ArtifactStore) {
    super({
      agentId: "specialist",
      role:    "specialist",
      llm:     new StubLLMAdapter("specialist-llm", "[SPEC]"),
      store,
      systemPrompt: "You summarize content with precision and brevity.",
      // Deny any write_artifact consent from untrusted agents
      consentPolicy: (req: ConsentRequest): ConsentDecision => {
        if (req.action === "write_artifact" && req.requestingAgent === "unknown-agent") {
          log("SPEC", C.red, `Denying consent: ${req.requestingAgent} wants ${req.action}`);
          return "denied";
        }
        return "granted";
      },
    });
  }

  async handleMessage(msg: AgentMessage): Promise<AgentMessage> {
    log("SPEC", C.green, `Handling task from ${msg.from}:`, JSON.stringify(msg.payload));

    const result = await this.llm.complete([
      { role: "system",  content: this.systemPrompt },
      { role: "user",    content: JSON.stringify(msg.payload) },
    ]);

    log("SPEC", C.green, `LLM result: ${result.text}`);

    // Seal a result artifact
    const artifact = await this.store.put({
      createdBy:  this.agentId,
      taskTreeId: msg.context.taskTreeId,
      content:    { summary: result.text, source: msg.payload },
    });
    const sealed = await this.store.seal(artifact.id, this.agentId);
    log("SPEC", C.green, `Sealed artifact ${sealed.id}`);

    return this.reply(msg, {
      summary:    result.text,
      artifactId: sealed.id,
      tokenUsage: result.usage,
    });
  }
}

// ─── GatekeeperAgent (demonstrates refusal) ───────────────────────────────────
class GatekeeperAgent extends BaseAgent {
  constructor(store: ArtifactStore) {
    super({
      agentId: "gatekeeper",
      role:    "gatekeeper",
      llm:     new StubLLMAdapter("gk-llm", "[GK]"),
      store,
      systemPrompt: "You enforce policy. You refuse all incoming tasks.",
      consentPolicy: (): ConsentDecision => "denied",
    });
  }

  async handleMessage(msg: AgentMessage): Promise<AgentMessage> {
    // Should never be reached if consent is enforced
    return this.reply(msg, { error: "Should not have reached gatekeeper" }, "error");
  }
}

// ─── Main ─────────────────────────────────────────────────────────────────────
async function main() {
  console.log(`\n${C.bold}${C.magenta}╔══════════════════════════════════════════╗`);
  console.log(`║          agent-mesh-mcp hello-mesh      ║`);
  console.log(`╚══════════════════════════════════════════╝${C.reset}\n`);

  // 1. Bootstrap infrastructure
  const store   = new InMemoryArtifactStore();
  const locks   = new InProcRWPhaseLockManager((lockId, res, holder, mode) => {
    log("LOCKS", C.yellow, `Lock expired: ${lockId} (${mode} on ${res} by ${holder})`);
  });

  const router  = new ConsentEnforcingRouter(store, {
    requireExplicitConsent: false, // permissive for hello-mesh
    consentCacheTtlMs: 60_000,
  });

  // 2. Register agents
  const orchestrator = new OrchestratorAgent(store);
  const specialist   = new SpecialistAgent(store);
  const gatekeeper   = new GatekeeperAgent(store);

  router.register(orchestrator);
  router.register(specialist);
  router.register(gatekeeper);

  log("GATEWAY", C.blue, "Agents registered:", ["orchestrator", "specialist", "gatekeeper"].join(", "));

  // ── Demo 1: Normal task flow ─────────────────────────────────────────────
  console.log(`\n${C.bold}── Demo 1: Normal task routing ────────────────────────────${C.reset}`);

  const taskTreeId = randomUUID();
  const taskMsg: AgentMessage = {
    id:        randomUUID(),
    from:      "gateway",
    to:        "orchestrator",
    type:      "task",
    payload:   {
      task:    "Summarize the agent-mesh-mcp architecture",
      details: "Focus on the consent router and RW phase locks",
    },
    context:   { taskTreeId, capabilityTags: ["summarize", "architecture"] },
    timestamp: Date.now(),
  };

  log("GATEWAY", C.blue, `Routing task ${taskMsg.id} → orchestrator`);
  const reply1 = await router.route(taskMsg);
  log("GATEWAY", C.blue, `Reply from orchestrator:`, JSON.stringify(reply1.payload, null, 2));

  // ── Demo 2: RW Phase Lock ────────────────────────────────────────────────
  console.log(`\n${C.bold}── Demo 2: RW Phase Lock contention ───────────────────────${C.reset}`);

  const resourceId = "artifact:shared-doc";
  log("LOCKS", C.yellow, `Acquiring READ lock on ${resourceId}`);
  const readLock1 = await locks.acquire(resourceId, "read", "agent-A");
  const readLock2 = await locks.acquire(resourceId, "read", "agent-B");
  log("LOCKS", C.yellow, `Two readers active. Snapshot:`, JSON.stringify(locks.snapshot()));

  // Write lock will queue until readers release
  const writePromise = locks.acquire(resourceId, "write", "agent-C").then((wl) => {
    log("LOCKS", C.yellow, `Write lock granted to agent-C`);
    return wl.release();
  });

  log("LOCKS", C.yellow, `Releasing reader locks...`);
  await readLock1.release();
  await readLock2.release();
  await writePromise;
  log("LOCKS", C.yellow, `All locks released. Snapshot:`, JSON.stringify(locks.snapshot()));

  // ── Demo 3: Consent refusal fossil ──────────────────────────────────────
  console.log(`\n${C.bold}── Demo 3: Refusal fossil (unknown target) ─────────────────${C.reset}`);

  const badMsg: AgentMessage = {
    id:        randomUUID(),
    from:      "gateway",
    to:        "nonexistent-agent",
    type:      "task",
    payload:   { task: "This should fail" },
    context:   { taskTreeId },
    timestamp: Date.now(),
  };

  const refusal = await router.route(badMsg);
  log("GATEWAY", C.red, `Refusal received:`, JSON.stringify(refusal.payload));

  // ── Print fossil chain ───────────────────────────────────────────────────
  console.log(`\n${C.bold}── Fossil Chain ────────────────────────────────────────────${C.reset}`);
  const fossils = await store.fossils();
  fossils.forEach((f, i) => {
    console.log(
      `  ${C.dim}[${i}]${C.reset} ${C.bold}${f.event}${C.reset}` +
      ` | agent=${f.agentId}` +
      ` | hash=${f.chainHash.slice(0, 12)}...`
    );
  });

  // ── Store integrity ──────────────────────────────────────────────────────
  const snap = (store as InMemoryArtifactStore).snapshot();
  console.log(`\n${C.bold}── Store Snapshot ──────────────────────────────────────────${C.reset}`);
  console.log(`  artifacts=${snap.artifactCount}  fossils=${snap.fossilCount}  chainValid=${snap.chainValid}`);

  console.log(`\n${C.bold}${C.green}✓ hello-mesh complete${C.reset}\n`);
}

main().catch((err) => {
  console.error(`${C.red}${C.bold}Fatal error:${C.reset}`, err);
  process.exit(1);
});
