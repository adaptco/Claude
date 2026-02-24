import { BaseAgent, type AgentMessage, type ArtifactStore, type ConsentDecision, type ConsentRequest } from "@agent-mesh/core";
import { StubLLMAdapter } from "@agent-mesh/adapter-stub";

class MeshRoleAgent extends BaseAgent {
  constructor(
    agentId: "orchestrator" | "specialist" | "gatekeeper",
    role: "orchestrator" | "specialist" | "gatekeeper",
    store: ArtifactStore
  ) {
    const consentPolicy =
      agentId === "gatekeeper"
        ? (_req: ConsentRequest): ConsentDecision => "denied"
        : (_req: ConsentRequest): ConsentDecision => "granted";

    super({
      agentId,
      role,
      llm: new StubLLMAdapter(`${agentId}-llm`, `[${agentId.toUpperCase()}]`),
      store,
      systemPrompt: `You are ${agentId}, role ${role}.`,
      consentPolicy,
    });
  }

  async handleMessage(msg: AgentMessage): Promise<AgentMessage> {
    const payloadText = typeof msg.payload === "string" ? msg.payload : JSON.stringify(msg.payload);
    const completion = await this.llm.complete([
      { role: "system", content: this.systemPrompt },
      { role: "user", content: payloadText },
    ]);
    const embedding = await this.llm.embeddings(payloadText);
    const artifact = await this.store.put({
      createdBy: this.agentId,
      taskTreeId: msg.context.taskTreeId,
      content: { input: msg.payload, output: completion.text },
      embedding,
    });
    const finalArtifact = this.agentId === "specialist" ? await this.store.seal(artifact.id, this.agentId) : artifact;
    return this.reply(msg, {
      agentId: this.agentId,
      role: this.role,
      summary: completion.text,
      artifactId: finalArtifact.id,
      artifactStatus: finalArtifact.status,
    });
  }
}

export function createDefaultAgents(store: ArtifactStore): MeshRoleAgent[] {
  return [
    new MeshRoleAgent("orchestrator", "orchestrator", store),
    new MeshRoleAgent("specialist", "specialist", store),
    new MeshRoleAgent("gatekeeper", "gatekeeper", store),
  ];
}
