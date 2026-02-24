# agent-mesh-mcp

LLM-agnostic multi-agent orchestration with consent-enforced routing, fossil-chain audit logs, and a phased A2A digital-twin integration.

## Quickstart

```bash
pnpm install
pnpm --filter @agent-mesh/gateway hello
```

## Hybrid MCP + Sidecar (Phase One)

```bash
# terminal A
pnpm sidecar:serve

# terminal B
pnpm mcp:serve
```

Defaults:
- Sidecar URL: `http://127.0.0.1:8090` (`SIDECAR_BASE_URL` to override)
- Sidecar host/port: `SIDECAR_HOST` / `SIDECAR_PORT`
- Embeddings: OpenAI `text-embedding-3-small` with deterministic hash fallback when `OPENAI_API_KEY` is unset

## Tools Exposed by MCP Server

- `agents.list`
- `agents.send`
- `artifacts.seal`
- `artifacts.query`
- `fossils.list`
- `agents.spawn`
- `repo.search`
- `twin.get_state`
- `twin.get_tasks`

## Package Map

| Package | Purpose |
|---|---|
| `@agent-mesh/core` | Shared types and base agent |
| `@agent-mesh/mcp-router` | Consent router and lock manager |
| `@agent-mesh/artifact-store` | In-memory artifact and fossil chain store |
| `@agent-mesh/adapter-stub` | Deterministic no-network LLM adapter |
| `@agent-mesh/mcp-bridge` | Strict HTTP bridge to sidecar |
| `apps/gateway` | Demo flow (`hello-mesh`) |
| `apps/mcp-server` | MCP stdio server |
| `services/digital-twin-sidecar` | Python repo-search + twin-state sidecar |

## Differential Artifacts

Run:

```bash
python scripts/generate_a2a_differential.py
```

Outputs:
- `docs/a2a_digital_twin_differential.md`
- `docs/a2a_digital_twin_differential.json`
