import { randomUUID } from "node:crypto";

import { InMemoryArtifactStore } from "@agent-mesh/artifact-store";
import type { Agent, AgentMessage } from "@agent-mesh/core";
import { SidecarClient, type BridgeErrorCode, BridgeError } from "@agent-mesh/mcp-bridge";
import { ConsentEnforcingRouter } from "@agent-mesh/mcp-router";

import { createDefaultAgents } from "./agents.js";

interface RuntimeConfig {
  sidecarBaseUrl?: string;
}

export interface RuntimeSidecarError {
  code: BridgeErrorCode;
  message: string;
}

export interface SpawnResult {
  selectedAgent: string;
  score: number;
  reply: AgentMessage;
  sidecar: {
    assignment?: RuntimeSidecarError;
    completion?: RuntimeSidecarError;
  };
}

export interface RankedAgentCandidate {
  agentId: string;
  vector: number[];
}

export function dot(a: number[], b: number[]): number {
  let total = 0;
  const len = Math.min(a.length, b.length);
  for (let i = 0; i < len; i += 1) total += a[i] * b[i];
  return total;
}

export function selectBestAgent(taskVector: number[], candidates: RankedAgentCandidate[]): {
  agentId: string;
  score: number;
} {
  if (!candidates.length) {
    throw new Error("no agents registered");
  }

  let bestId = candidates[0].agentId;
  let bestScore = dot(taskVector, candidates[0].vector);

  for (const candidate of candidates.slice(1)) {
    const score = dot(taskVector, candidate.vector);
    if (score > bestScore) {
      bestScore = score;
      bestId = candidate.agentId;
    }
  }
  return { agentId: bestId, score: bestScore };
}

function asSidecarError(err: unknown): RuntimeSidecarError | undefined {
  if (err instanceof BridgeError) {
    return { code: err.code, message: err.message };
  }
  return undefined;
}

export class McpMeshRuntime {
  readonly store = new InMemoryArtifactStore();
  readonly router = new ConsentEnforcingRouter(this.store, {
    requireExplicitConsent: false,
    consentCacheTtlMs: 60_000,
  });
  readonly sidecar: SidecarClient;
  readonly agents = new Map<string, Agent>();

  constructor(config: RuntimeConfig = {}) {
    this.sidecar = new SidecarClient({ baseUrl: config.sidecarBaseUrl ?? "http://127.0.0.1:8090", timeoutMs: 2000 });
    for (const agent of createDefaultAgents(this.store)) {
      this.agents.set(agent.agentId, agent);
      this.router.register(agent);
    }
  }

  listAgents() {
    return [...this.agents.values()].map((agent) => ({
      agentId: agent.agentId,
      role: agent.role,
    }));
  }

  async sendMessage(input: {
    to: string;
    type: "task" | "query" | "artifact";
    payload: Record<string, unknown>;
    taskTreeId?: string;
  }): Promise<AgentMessage> {
    const msg: AgentMessage = {
      id: randomUUID(),
      from: "mcp-client",
      to: input.to,
      type: input.type,
      payload: input.payload,
      context: { taskTreeId: input.taskTreeId ?? randomUUID() },
      timestamp: Date.now(),
    };
    return this.router.route(msg);
  }

  async sealArtifact(artifactId: string, sealedBy = "mcp-server") {
    return this.store.seal(artifactId, sealedBy);
  }

  async queryArtifacts(text: string, topK = 5) {
    const firstAgent = this.agents.values().next().value as Agent | undefined;
    if (!firstAgent) return [];
    const vector = await firstAgent.llm.embeddings(text);
    return this.store.query(vector, topK);
  }

  async listFossils() {
    return this.store.fossils();
  }

  async spawnAgent(input: { task: string; agentId?: string; taskTreeId?: string }): Promise<SpawnResult> {
    const taskTreeId = input.taskTreeId ?? randomUUID();
    const firstAgent = this.agents.values().next().value as Agent | undefined;
    if (!firstAgent) throw new Error("no agents registered");

    const queryVector = await firstAgent.llm.embeddings(input.task);
    const candidates: RankedAgentCandidate[] = [];
    for (const agent of this.agents.values()) {
      candidates.push({ agentId: agent.agentId, vector: await agent.capabilityVector() });
    }

    let selectedAgent = input.agentId ?? "";
    let score = 1.0;
    if (selectedAgent) {
      if (!this.agents.has(selectedAgent)) {
        throw new Error(`unknown agent: ${selectedAgent}`);
      }
    } else {
      const ranked = selectBestAgent(queryVector, candidates);
      selectedAgent = ranked.agentId;
      score = ranked.score;
    }

    let assignmentError: RuntimeSidecarError | undefined;
    try {
      await this.sidecar.notifyTaskAssigned({ taskId: taskTreeId, agentId: selectedAgent, taskName: input.task });
    } catch (err) {
      assignmentError = asSidecarError(err);
    }

    const reply = await this.sendMessage({
      to: selectedAgent,
      type: "task",
      payload: { task: input.task },
      taskTreeId,
    });

    const fossils = await this.store.fossils();
    const fossilHash = fossils.length ? fossils[fossils.length - 1].chainHash : "";

    let completionError: RuntimeSidecarError | undefined;
    try {
      await this.sidecar.notifyTaskCompleted({ taskId: taskTreeId, fossilHash });
    } catch (err) {
      completionError = asSidecarError(err);
    }

    return {
      selectedAgent,
      score,
      reply,
      sidecar: {
        assignment: assignmentError,
        completion: completionError,
      },
    };
  }

  async repoSearch(query: string, topK = 8, agentFilter = "") {
    return this.sidecar.searchRepo(query, { topK, agentFilter });
  }

  async twinState() {
    return this.sidecar.getTwinState();
  }

  async twinTasks(status = "") {
    return this.sidecar.getTwinTasks(status);
  }
}

export function createRuntime(config: RuntimeConfig = {}) {
  return new McpMeshRuntime(config);
}
