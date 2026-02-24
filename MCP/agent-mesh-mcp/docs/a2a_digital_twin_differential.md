# A2A Digital Twin Differential

Generated: 2026-02-24T23:15:57.246906+00:00

## Scope
- MCP root: `C:\Users\eqhsp\Downloads\Claude\MCP\agent-mesh-mcp`
- A2A root: `C:\Users\eqhsp\Downloads\Claude\Airtable\a2a-digital-twin\a2a-digital-twin`

## File Inventory
- MCP files: **49**
- A2A files: **11**
- Common relative paths: **0**
- MCP-only relative paths: **49**
- A2A-only relative paths: **11**

## Tool Surfaces
- MCP tools: `agents.list`, `agents.send`, `agents.spawn`, `artifacts.query`, `artifacts.seal`, `fossils.list`, `repo.search`, `twin.get_state`, `twin.get_tasks`
- A2A tools: `get_repo_status`, `get_twin_state`, `get_twin_tasks`, `git_commit`, `list_agents`, `list_directory`, `read_file`, `run_tests`, `search_repo`, `search_web`, `spawn_agent`, `sync_tasks`, `write_file`

## Phase-One Tool Mapping
| MCP Tool | A2A Source |
|---|---|
| `agents.spawn` | `spawn_agent` |
| `repo.search` | `search_repo` |
| `twin.get_state` | `get_twin_state` |
| `twin.get_tasks` | `get_twin_tasks` |

## Common File Sample
- (none)

## MCP-only File Sample
- `.github/workflows/ci.yml`
- `README.md`
- `apps/gateway/package.json`
- `apps/gateway/src/hello-mesh.ts`
- `apps/gateway/tsconfig.json`
- `apps/mcp-server/package.json`
- `apps/mcp-server/src/agents.ts`
- `apps/mcp-server/src/runtime.ts`
- `apps/mcp-server/src/server.ts`
- `apps/mcp-server/test/runtime.test.ts`
- `apps/mcp-server/tsconfig.json`
- `docs/a2a_digital_twin_differential.json`

## A2A-only File Sample
- `agents/adk_subagent_spawner.py`
- `bootstrap_digital_twin.py`
- `digital_twin/twin_registry.py`
- `docs/ARCHITECTURE.md`
- `docs/SETUP.md`
- `integrations/airtable/task_schema.py`
- `integrations/github/a2a_twin_pipeline.yml`
- `integrations/office/graph_checkpoint.py`
- `integrations/perplexity/search_agent.py`
- `mcp_extensions/claude_code_mcp_server.py`
- `rag/vertical_tensor_slice.py`
