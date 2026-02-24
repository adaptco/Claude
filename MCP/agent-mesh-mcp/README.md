# agent-mesh-mcp

LLM-agnostic multi-agent orchestration using Model Context Protocol.  
Inspired by Claude Cowork — extended with peer-to-peer agent messaging, consent enforcement, RW phase locks, and a tamper-evident fossil chain.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        apps/gateway                         │
│   HTTP/WS entry point → AgentMessage → ConsentRouter        │
└────────────────────────┬────────────────────────────────────┘
                         │
              ┌──────────▼──────────┐
              │  ConsentEnforcing   │  ← packages/mcp-router
              │      Router         │
              │  + RW Phase Locks   │
              └──┬──────────────┬───┘
                 │              │
        ┌────────▼───┐   ┌──────▼──────┐
        │Orchestrator│   │ Specialist  │  ← Any role
        │   Agent    │   │   Agent     │
        └────────────┘   └─────────────┘
                 │              │
              ┌──▼──────────────▼──┐
              │  InMemoryArtifact  │  ← packages/artifact-store
              │      Store         │
              │  + Fossil Chain    │
              └────────────────────┘
```

## Key Invariants

- **Consent is unbypassable** — every message is consent-checked before delivery
- **Every event is fossiled** — append-only, SHA-256 chain-hashed audit log
- **RW phase locks** — write-preference, TTL-expiry, in-proc (swap to Redis/etcd)
- **LLM-agnostic** — implement `LLMAdapter` for any provider

---

## Quickstart

```bash
# 1. Clone & install
git clone https://github.com/YOUR_ORG/agent-mesh-mcp
cd agent-mesh-mcp
pnpm install

# 2. Run hello-mesh (no API keys needed)
pnpm --filter @agent-mesh/gateway hello
```

**Expected output:**
- Demo 1: Orchestrator receives task → routes subtask → Specialist summarizes → seals artifact
- Demo 2: RW lock contention — two readers block a writer until they release
- Demo 3: Unknown target → consent refusal fossil written
- Full fossil chain printed with chain hashes

---

## Package Map

| Package | Purpose |
|---|---|
| `@agent-mesh/core` | All shared types + `BaseAgent` class |
| `@agent-mesh/mcp-router` | `ConsentEnforcingRouter` + `InProcRWPhaseLockManager` |
| `@agent-mesh/artifact-store` | `InMemoryArtifactStore` with fossil chain + cosine search |
| `@agent-mesh/adapter-stub` | Zero-network LLM adapter for testing |
| `@agent-mesh/adapter-openai` | OpenAI adapter (skeleton — add your key) |
| `@agent-mesh/adapter-anthropic` | Anthropic adapter (skeleton — add your key) |
| `apps/gateway` | Entry point + `hello-mesh.ts` runnable |

---

## Adding a Real LLM Adapter

```typescript
// packages/adapters/openai/src/openai-adapter.ts
import OpenAI from "openai";
import type { LLMAdapter, Message } from "@agent-mesh/core";

export class OpenAIAdapter implements LLMAdapter {
  readonly id = "openai";
  private client: OpenAI;

  constructor(apiKey: string, private model = "gpt-4o") {
    this.client = new OpenAI({ apiKey });
  }

  async complete(messages: Message[]) {
    const res = await this.client.chat.completions.create({
      model: this.model,
      messages: messages.map(m => ({ role: m.role as any, content: m.content })),
    });
    return { text: res.choices[0].message.content ?? "" };
  }

  async *stream(messages: Message[]) { /* ... */ yield { type: "done" as const, result: { text: "" } }; }

  async embeddings(text: string) {
    const res = await this.client.embeddings.create({ model: "text-embedding-3-small", input: text });
    return res.data[0].embedding;
  }
}
```

---

## Roadmap

- [ ] Replace `InMemoryArtifactStore` with Postgres + pgvector
- [ ] Replace `InProcRWPhaseLockManager` with Redis Redlock
- [ ] Add WebSocket gateway for real-time agent streaming
- [ ] Semantic router (cosine capability matching at route time)
- [ ] React web UI (Cowork-style task board)
- [ ] MCP server exposing `agents.send`, `artifacts.query` as tools
- [ ] OpenAI / Anthropic / Gemini / Ollama adapter implementations

---

## Contributing

1. Add an adapter → implement `LLMAdapter` in `packages/adapters/<name>/`
2. Add an agent role → extend `BaseAgent` from `@agent-mesh/core`
3. Swap the store → implement `ArtifactStore` interface
4. Swap the locks → implement `LockHandle` interface

The consent router and fossil chain are intentionally **not pluggable** — they are the kernel.
