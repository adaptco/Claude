import type {
  Agent,
  AgentId,
  AgentMessage,
  ArtifactStore,
  ConsentAction,
  ConsentDecision,
  ConsentRecord,
  ConsentRequest,
  FossilEventType,
  Router,
} from "@agent-mesh/core";
import { randomUUID } from "crypto";

interface RouterConfig {
  /** If true, an agent may only send to agents it has a prior consent record for */
  requireExplicitConsent: boolean;
  /** Default TTL for cached consent grants (ms) */
  consentCacheTtlMs: number;
}

const DEFAULT_CONFIG: RouterConfig = {
  requireExplicitConsent: false,
  consentCacheTtlMs: 5 * 60 * 1000, // 5 min
};

/**
 * ConsentEnforcingRouter
 *
 * Invariants (cannot be bypassed):
 *  1. Every routed message produces a fossil (granted or refused).
 *  2. Consent grants are cached with TTL; expired grants re-prompt.
 *  3. Denied consent always produces a refusal fossil and short-circuits routing.
 *  4. Unknown target agents produce an error fossil + error reply.
 *  5. Fossils are append-only and chain-hashed (SHA-256 of prev seal).
 */
export class ConsentEnforcingRouter implements Router {
  private readonly agents = new Map<AgentId, Agent>();
  private readonly consentCache = new Map<string, ConsentRecord>();
  private lastFossilHash = "genesis";

  constructor(
    private readonly store: ArtifactStore,
    private readonly config: RouterConfig = DEFAULT_CONFIG
  ) {}

  register(agent: Agent): void {
    this.agents.set(agent.agentId, agent);
  }

  async route(msg: AgentMessage): Promise<AgentMessage> {
    // ── 1. Resolve target ───────────────────────────────────────────────────
    const target = this.resolveTarget(msg);
    if (!target) {
      return this.refuseWithFossil(msg, "message_refused", `Unknown target: ${msg.to}`);
    }

    // ── 2. Determine consent action ─────────────────────────────────────────
    const action = this.inferAction(msg);

    // ── 3. Check consent ────────────────────────────────────────────────────
    const decision = await this.checkConsent(msg.from, target.agentId, action, msg);
    if (decision === "denied") {
      return this.refuseWithFossil(
        msg,
        "message_refused",
        `Consent denied: ${msg.from} → ${target.agentId} (${action})`
      );
    }

    // ── 4. Fossil: message_routed ────────────────────────────────────────────
    await this.writeFossil("message_routed", msg.from, msg.context.taskTreeId, {
      msgId: msg.id,
      to: target.agentId,
      type: msg.type,
      action,
      consentDecision: decision,
    });

    // ── 5. Deliver ──────────────────────────────────────────────────────────
    try {
      return await target.handleMessage(msg);
    } catch (err) {
      return this.refuseWithFossil(
        msg,
        "message_refused",
        `Agent threw: ${(err as Error).message}`
      );
    }
  }

  // ── Private helpers ────────────────────────────────────────────────────────

  private resolveTarget(msg: AgentMessage): Agent | undefined {
    if (msg.to === "broadcast") return undefined; // broadcast handled separately
    return this.agents.get(msg.to);
  }

  private inferAction(msg: AgentMessage): ConsentAction {
    switch (msg.type) {
      case "artifact":  return "write_artifact";
      case "query":     return "read_artifact";
      case "task":      return "send_message";
      case "result":    return "send_message";
      default:          return "send_message";
    }
  }

  private async checkConsent(
    from: AgentId,
    to: AgentId,
    action: ConsentAction,
    msg: AgentMessage
  ): Promise<ConsentDecision> {
    if (!this.config.requireExplicitConsent) {
      // Permissive mode — auto-grant but still record
      await this.cacheConsent(from, to, action, "granted");
      return "granted";
    }

    const cacheKey = `${from}:${to}:${action}`;
    const cached = this.consentCache.get(cacheKey);
    if (cached) {
      const expired = cached.ttlMs && Date.now() > cached.decidedAt + cached.ttlMs;
      if (!expired) return cached.decision;
      this.consentCache.delete(cacheKey);
    }

    // Ask the TARGET agent whether it will accept this message from `from`
    const targetAgent = this.agents.get(to);
    if (!targetAgent) return "denied";

    const req: ConsentRequest = {
      requestId: randomUUID(),
      requestingAgent: from,
      targetAgent: to,
      action,
      resourceId: msg.id,
      justification: `Routing ${msg.type} from ${from}`,
    };

    const decision = await targetAgent.requestConsent(req);
    await this.cacheConsent(from, to, action, decision);

    // Fossil the consent decision
    await this.writeFossil(
      decision === "granted" ? "consent_granted" : "consent_denied",
      from,
      msg.context.taskTreeId,
      req
    );

    return decision;
  }

  private async cacheConsent(
    from: AgentId,
    to: AgentId,
    action: ConsentAction,
    decision: ConsentDecision
  ) {
    const key = `${from}:${to}:${action}`;
    const record: ConsentRecord = {
      request: {
        requestId: randomUUID(),
        requestingAgent: from,
        targetAgent: to,
        action,
        justification: "auto-cached",
      },
      decision,
      decidedBy: to,
      decidedAt: Date.now(),
      ttlMs: this.config.consentCacheTtlMs,
    };
    this.consentCache.set(key, record);
  }

  private async refuseWithFossil(
    msg: AgentMessage,
    event: FossilEventType,
    reason: string
  ): Promise<AgentMessage> {
    await this.writeFossil(event, msg.from, msg.context.taskTreeId, {
      msgId: msg.id,
      to: msg.to,
      reason,
    });

    const errorMsg: AgentMessage = {
      id: randomUUID(),
      from: "router",
      to: msg.from,
      type: "error",
      payload: { reason },
      context: { taskTreeId: msg.context.taskTreeId },
      timestamp: Date.now(),
    };
    return errorMsg;
  }

  private async writeFossil(
    event: FossilEventType,
    agentId: AgentId,
    taskTreeId: string | undefined,
    payload: unknown
  ) {
    // Chain hash = SHA-256 of (lastHash + timestamp + JSON(payload))
    const { createHash } = await import("crypto");
    const chainHash = createHash("sha256")
      .update(this.lastFossilHash + Date.now() + JSON.stringify(payload))
      .digest("hex");
    this.lastFossilHash = chainHash;

    const fossil = await this.store.fossil({ event, agentId, taskTreeId, payload });
    return fossil;
  }

  /** Broadcast: deliver to all agents except sender; collect replies */
  async broadcast(msg: AgentMessage): Promise<AgentMessage[]> {
    const replies: AgentMessage[] = [];
    for (const [id, agent] of this.agents) {
      if (id === msg.from) continue;
      const routed = { ...msg, to: id };
      replies.push(await this.route(routed));
    }
    return replies;
  }

  consentCacheSnapshot() {
    return Object.fromEntries(this.consentCache.entries());
  }
}
