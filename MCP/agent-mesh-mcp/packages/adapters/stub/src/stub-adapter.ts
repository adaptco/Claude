import type {
  LLMAdapter,
  Message,
  Tool,
  CompletionResult,
  StreamChunk,
} from "@agent-mesh/core";
import { createHash } from "crypto";

/**
 * StubLLMAdapter
 *
 * Fully deterministic, zero-network LLM adapter for testing / hello-mesh.
 * Embeddings are 64-dim hashes of the input text (stable across runs).
 */
export class StubLLMAdapter implements LLMAdapter {
  readonly id: string;

  constructor(id = "stub", private readonly replyPrefix = "[STUB]") {
    this.id = id;
  }

  async complete(messages: Message[], _tools?: Tool[]): Promise<CompletionResult> {
    const last = messages[messages.length - 1];
    const text = `${this.replyPrefix} Echo: "${last?.content?.slice(0, 80) ?? ""}"`;
    return {
      text,
      usage: { promptTokens: last?.content?.length ?? 0, completionTokens: text.length },
    };
  }

  async *stream(messages: Message[], tools?: Tool[]): AsyncIterable<StreamChunk> {
    const result = await this.complete(messages, tools);
    for (const ch of result.text.split(" ")) {
      yield { type: "delta", delta: ch + " " };
      await new Promise((r) => setTimeout(r, 10));
    }
    yield { type: "done", result };
  }

  async embeddings(text: string): Promise<number[]> {
    // Deterministic 64-dim embedding from SHA-256 hash bytes
    const hash = createHash("sha256").update(text).digest();
    const vec: number[] = [];
    for (let i = 0; i < 64; i++) {
      vec.push((hash[i % 32] / 255) * 2 - 1); // normalise to [-1, 1]
    }
    // L2-normalise
    const norm = Math.sqrt(vec.reduce((s, v) => s + v * v, 0));
    return vec.map((v) => v / norm);
  }
}
