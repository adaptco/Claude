// ─── Identifiers ─────────────────────────────────────────────────────────────
export type AgentId = string;
export type TaskId  = string;
export type ArtifactId = string;

// ─── LLM surface ─────────────────────────────────────────────────────────────
export interface Message {
  role: "system" | "user" | "assistant" | "tool";
  content: string;
  toolCallId?: string;
  name?: string;
}

export interface Tool {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>; // JSON Schema
}

export interface CompletionResult {
  text: string;
  toolCalls?: ToolCall[];
  usage?: { promptTokens: number; completionTokens: number };
}

export interface ToolCall {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
}

export interface StreamChunk {
  type: "delta" | "tool_call" | "done";
  delta?: string;
  toolCall?: ToolCall;
  result?: CompletionResult;
}

// ─── LLM Adapter interface ───────────────────────────────────────────────────
export interface LLMAdapter {
  readonly id: string;
  complete(messages: Message[], tools?: Tool[]): Promise<CompletionResult>;
  stream(messages: Message[], tools?: Tool[]): AsyncIterable<StreamChunk>;
  embeddings(text: string): Promise<number[]>;
}

// ─── Agent roles ─────────────────────────────────────────────────────────────
export type AgentRole =
  | "orchestrator"
  | "specialist"
  | "reviewer"
  | "executor"
  | "gatekeeper";

// ─── MCP Agent Message ───────────────────────────────────────────────────────
export type MessageType =
  | "task"
  | "result"
  | "artifact"
  | "query"
  | "consent_request"
  | "consent_grant"
  | "consent_deny"
  | "error";

export interface EmbeddingContext {
  vector?: number[];          // semantic embedding of payload
  capabilityTags?: string[];  // human-readable capability hints
  taskTreeId?: TaskId;        // links message to a parent task tree
}

export interface AgentMessage {
  id: string;
  from: AgentId;
  to: AgentId | "broadcast";
  type: MessageType;
  payload: unknown;
  context: EmbeddingContext;
  timestamp: number;
}

// ─── Consent ─────────────────────────────────────────────────────────────────
export type ConsentAction =
  | "read_artifact"
  | "write_artifact"
  | "seal_artifact"
  | "send_message"
  | "spawn_agent"
  | "access_tool";

export interface ConsentRequest {
  requestId: string;
  requestingAgent: AgentId;
  targetAgent?: AgentId;
  action: ConsentAction;
  resourceId?: string;
  justification: string;
}

export type ConsentDecision = "granted" | "denied" | "deferred";

export interface ConsentRecord {
  request: ConsentRequest;
  decision: ConsentDecision;
  decidedBy: AgentId;
  decidedAt: number;
  ttlMs?: number;
}

// ─── Fossil / Audit log ──────────────────────────────────────────────────────
export type FossilEventType =
  | "consent_granted"
  | "consent_denied"
  | "message_routed"
  | "message_refused"
  | "artifact_sealed"
  | "artifact_written"
  | "lock_acquired"
  | "lock_released"
  | "lock_timeout";

export interface FossilRecord {
  fossilId: string;
  event: FossilEventType;
  agentId: AgentId;
  taskTreeId?: TaskId;
  payload: unknown;
  sealedAt: number;
  /** SHA-256 of (prev.sealedAt + JSON.stringify(payload)) — chain integrity */
  chainHash: string;
}

// ─── Artifact ────────────────────────────────────────────────────────────────
export type ArtifactStatus = "draft" | "sealed";

export interface Artifact {
  id: ArtifactId;
  createdBy: AgentId;
  taskTreeId?: TaskId;
  content: unknown;
  embedding?: number[];
  status: ArtifactStatus;
  createdAt: number;
  sealedAt?: number;
}

// ─── Phase-lock ──────────────────────────────────────────────────────────────
export type LockMode = "read" | "write";

export interface LockHandle {
  lockId: string;
  resourceId: string;
  mode: LockMode;
  holder: AgentId;
  acquiredAt: number;
  expiresAt: number;
  release(): Promise<void>;
}

// ─── Agent interface ─────────────────────────────────────────────────────────
export interface Agent {
  readonly agentId: AgentId;
  readonly role: AgentRole;
  readonly llm: LLMAdapter;
  readonly tools: Tool[];
  handleMessage(msg: AgentMessage): Promise<AgentMessage>;
  requestConsent(req: ConsentRequest): Promise<ConsentDecision>;
  capabilityVector(): Promise<number[]>; // for semantic routing
}

// ─── Router interface ─────────────────────────────────────────────────────────
export interface Router {
  register(agent: Agent): void;
  route(msg: AgentMessage): Promise<AgentMessage>;
}

// ─── Artifact store interface ─────────────────────────────────────────────────
export interface ArtifactStore {
  put(artifact: Omit<Artifact, "id" | "createdAt" | "status">): Promise<Artifact>;
  get(id: ArtifactId): Promise<Artifact | null>;
  seal(id: ArtifactId, sealedBy: AgentId): Promise<Artifact>;
  query(embeddingVector: number[], topK?: number): Promise<Artifact[]>;
  fossil(record: Omit<FossilRecord, "fossilId" | "sealedAt" | "chainHash">): Promise<FossilRecord>;
  fossils(): Promise<FossilRecord[]>;
}
