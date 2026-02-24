type UnknownRecord = Record<string, unknown>;

export type BridgeErrorCode =
  | "SIDECAR_UNAVAILABLE"
  | "SIDECAR_HTTP"
  | "SIDECAR_MALFORMED_RESPONSE";

export class BridgeError extends Error {
  readonly code: BridgeErrorCode;
  readonly status?: number;

  constructor(code: BridgeErrorCode, message: string, status?: number) {
    super(message);
    this.name = "BridgeError";
    this.code = code;
    this.status = status;
  }
}

export interface RepoSearchHit {
  key: string;
  file: string;
  score: number;
  text: string;
}

export interface RepoSearchResponse {
  ok: boolean;
  results: RepoSearchHit[];
  count: number;
}

export interface TwinStateResponse {
  ok: boolean;
  state: UnknownRecord;
}

export interface TwinTasksResponse {
  ok: boolean;
  tasks: UnknownRecord[];
}

export interface TwinMutationResponse {
  ok: boolean;
  task?: UnknownRecord;
  error?: string;
}

export interface SidecarClientConfig {
  baseUrl?: string;
  timeoutMs?: number;
}

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function validateRepoSearchResponse(value: unknown): value is RepoSearchResponse {
  if (!isRecord(value)) return false;
  if (typeof value.ok !== "boolean") return false;
  if (!Array.isArray(value.results)) return false;
  if (!isNumber(value.count)) return false;
  for (const hit of value.results) {
    if (!isRecord(hit)) return false;
    if (!isString(hit.key) || !isString(hit.file) || !isString(hit.text)) return false;
    if (!isNumber(hit.score)) return false;
  }
  return true;
}

function validateTwinStateResponse(value: unknown): value is TwinStateResponse {
  return isRecord(value) && typeof value.ok === "boolean" && isRecord(value.state);
}

function validateTwinTasksResponse(value: unknown): value is TwinTasksResponse {
  return (
    isRecord(value) &&
    typeof value.ok === "boolean" &&
    Array.isArray(value.tasks) &&
    value.tasks.every((item) => isRecord(item))
  );
}

function validateTwinMutationResponse(value: unknown): value is TwinMutationResponse {
  if (!isRecord(value) || typeof value.ok !== "boolean") return false;
  if ("task" in value && value.task !== undefined && !isRecord(value.task)) return false;
  if ("error" in value && value.error !== undefined && !isString(value.error)) return false;
  return true;
}

export class SidecarClient {
  readonly baseUrl: string;
  readonly timeoutMs: number;

  constructor(config: SidecarClientConfig = {}) {
    this.baseUrl = (config.baseUrl ?? "http://127.0.0.1:8090").replace(/\/+$/, "");
    this.timeoutMs = config.timeoutMs ?? 2000;
  }

  async searchRepo(
    query: string,
    options: { topK?: number; agentFilter?: string } = {}
  ): Promise<RepoSearchResponse> {
    return this.requestJson(
      "POST",
      "/v1/repo/search",
      {
        query,
        topK: options.topK ?? 8,
        agentFilter: options.agentFilter ?? "",
      },
      validateRepoSearchResponse
    );
  }

  async getTwinState(): Promise<TwinStateResponse> {
    return this.requestJson("GET", "/v1/twin/state", undefined, validateTwinStateResponse);
  }

  async getTwinTasks(status = ""): Promise<TwinTasksResponse> {
    const query = status ? `?status=${encodeURIComponent(status)}` : "";
    return this.requestJson("GET", `/v1/twin/tasks${query}`, undefined, validateTwinTasksResponse);
  }

  async notifyTaskAssigned(payload: {
    taskId: string;
    agentId: string;
    taskName?: string;
  }): Promise<TwinMutationResponse> {
    return this.requestJson(
      "POST",
      "/v1/twin/task-assigned",
      payload,
      validateTwinMutationResponse
    );
  }

  async notifyTaskCompleted(payload: {
    taskId: string;
    fossilHash?: string;
  }): Promise<TwinMutationResponse> {
    return this.requestJson(
      "POST",
      "/v1/twin/task-completed",
      payload,
      validateTwinMutationResponse
    );
  }

  private async requestJson<T>(
    method: "GET" | "POST",
    path: string,
    body: UnknownRecord | undefined,
    validator: (value: unknown) => value is T
  ): Promise<T> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const res = await fetch(`${this.baseUrl}${path}`, {
        method,
        headers: body ? { "content-type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });

      if (!res.ok) {
        const text = await res.text().catch(() => "");
        throw new BridgeError(
          "SIDECAR_HTTP",
          `sidecar request failed (${res.status}) ${text}`.trim(),
          res.status
        );
      }

      let json: unknown;
      try {
        json = await res.json();
      } catch {
        throw new BridgeError("SIDECAR_MALFORMED_RESPONSE", "sidecar returned non-JSON payload");
      }

      if (!validator(json)) {
        throw new BridgeError(
          "SIDECAR_MALFORMED_RESPONSE",
          `sidecar response did not match expected schema for ${method} ${path}`
        );
      }

      return json;
    } catch (err) {
      if (err instanceof BridgeError) {
        throw err;
      }
      if (err instanceof Error && err.name === "AbortError") {
        throw new BridgeError(
          "SIDECAR_UNAVAILABLE",
          `sidecar timeout after ${this.timeoutMs}ms for ${method} ${path}`
        );
      }
      throw new BridgeError(
        "SIDECAR_UNAVAILABLE",
        `sidecar unavailable for ${method} ${path}: ${(err as Error).message}`
      );
    } finally {
      clearTimeout(timeout);
    }
  }
}
