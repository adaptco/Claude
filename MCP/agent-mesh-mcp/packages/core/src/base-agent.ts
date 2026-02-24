import type {
  Agent,
  AgentId,
  AgentMessage,
  AgentRole,
  ArtifactStore,
  ConsentDecision,
  ConsentRequest,
  LLMAdapter,
  Tool,
} from "@agent-mesh/core";
import { randomUUID } from "crypto";

export interface BaseAgentConfig {
  agentId: AgentId;
  role: AgentRole;
  llm: LLMAdapter;
  tools?: Tool[];
  store: ArtifactStore;
  systemPrompt?: string;
  /**
   * Simple consent policy. Override in subclasses for fine-grained control.
   * Default: accept any request from any agent.
   */
  consentPolicy?: (req: ConsentRequest) => ConsentDecision | Promise<ConsentDecision>;
}

export abstract class BaseAgent implements Agent {
  readonly agentId: AgentId;
  readonly role: AgentRole;
  readonly llm: LLMAdapter;
  readonly tools: Tool[];
  protected readonly store: ArtifactStore;
  protected readonly systemPrompt: string;
  private readonly consentPolicy: (req: ConsentRequest) => ConsentDecision | Promise<ConsentDecision>;

  constructor(config: BaseAgentConfig) {
    this.agentId   = config.agentId;
    this.role      = config.role;
    this.llm       = config.llm;
    this.tools     = config.tools ?? [];
    this.store     = config.store;
    this.systemPrompt = config.systemPrompt ?? `You are ${config.agentId}, role: ${config.role}.`;
    this.consentPolicy = config.consentPolicy ?? (() => "granted");
  }

  async requestConsent(req: ConsentRequest): Promise<ConsentDecision> {
    return this.consentPolicy(req);
  }

  async capabilityVector(): Promise<number[]> {
    // Embed the system prompt as the agent's capability signature
    return this.llm.embeddings(this.systemPrompt);
  }

  /** Subclasses implement the actual task logic */
  abstract handleMessage(msg: AgentMessage): Promise<AgentMessage>;

  /** Helper: build a reply message */
  protected reply(
    original: AgentMessage,
    payload: unknown,
    type: AgentMessage["type"] = "result"
  ): AgentMessage {
    return {
      id: randomUUID(),
      from: this.agentId,
      to: original.from,
      type,
      payload,
      context: { taskTreeId: original.context.taskTreeId },
      timestamp: Date.now(),
    };
  }
}
