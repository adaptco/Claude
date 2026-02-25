# A2A Digital Twin — Full System Architecture
## Grounded in: github.com/adaptco-main/A2A_MCP

---

## Mental Model

The GitHub repo IS the tensor space. Every file is a node. Every agent is a
query against that space. Tasks in Airtable define what queries to run. GitHub
Actions run those queries automatically. Microsoft Office checkpoints the
output. The browser is the execution surface for long-horizon tasks.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DIGITAL TWIN CONTROL PLANE                          │
│                                                                             │
│   Airtable (task/role/workflow schema)                                      │
│       │                                                                     │
│       ▼                                                                     │
│   GitHub Actions ──────────── triggers ──────────────────────────────────┐ │
│       │                                                                   │ │
│       ▼                                                                   │ │
│   MCPHub (orchestrator/main.py)  ◄── EXTENDED by mcp_extensions/          │ │
│       │                               claude_code_mcp_server.py           │ │
│       │                                                                   │ │
│       ├── IntentEngine (5-stage pipeline)                                 │ │
│       │       Manager → Orchestrator → Architect → Coder → Tester        │ │
│       │                                                                   │ │
│       ├── RAG Layer (rag/vertical_tensor_slice.py)                        │ │
│       │       GitHub repo → d=1536 normalized dot product vectors         │ │
│       │       Perplexity Search Agent fills gaps                          │ │
│       │                                                                   │ │
│       ├── A2A ADK (agents spawn subagents via A2A protocol)               │ │
│       │                                                                   │ │
│       ├── Digital Twin (digital_twin/twin_registry.py)                    │ │
│       │       Live mirror of repo state + task completion %               │ │
│       │                                                                   │ │
│       └── Checkpoints → Microsoft Office (integrations/office/)          │ │
│               Word: reports, Excel: metrics, Outlook: handoffs            │ │
│                                                                           │ │
│   Browser Tasks (Claude in Chrome / Playwright)  ◄────────────────────────┘ │
│       Long-horizon tasks decomposed into atomic browser actions             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Layer Breakdown

### Layer 0 — Repo as Tensor Space
- Source: `github.com/adaptco-main/A2A_MCP`
- Every `.py` file is chunked into semantic nodes
- Each node is embedded as d=1536 L2-normalized vector
- Similarity search = normalized dot product (equivalent to cosine, faster)
- Vertical slice = one column of the tensor matrix = one agent's context window

### Layer 1 — MCP Server (Claude Code replacement)
- `mcp_extensions/claude_code_mcp_server.py`
- Exposes tools: `read_file`, `write_file`, `run_tests`, `git_commit`, `search_repo`
- All tools are wrapped in the existing A2A consent/fossil pattern
- Any LLM can use it via MCP protocol (not just Claude)

### Layer 2 — RAG + Perplexity Search
- `rag/vertical_tensor_slice.py` — normalized dot product retrieval
- `integrations/perplexity/search_agent.py` — fills knowledge gaps
- Perplexity is registered as a tool in the MCP server
- Query → embed → dot product against repo vectors → top-k → Perplexity for web gaps

### Layer 3 — Airtable Task Schema
- Base: "A2A Digital Twin"
- Tables: Tasks, Roles, Workflows, Actions
- GitHub Actions reads Airtable via webhook on every push
- Tasks drive the IntentEngine pipeline

### Layer 4 — A2A ADK Subagents
- Extends existing `agents/` directory
- Each subagent is spawned from MCPHub with a capability vector
- A2A protocol: each agent exposes an Agent Card (JSON) + task endpoint

### Layer 5 — Digital Twin
- Live JSON mirror of repo state
- Tracks: file → embedding → last modified → agent responsible → task status
- Updated on every git push by GitHub Actions

### Layer 6 — Microsoft Office Checkpoints
- Word: auto-generated handoff docs from `HANDOFF.md` pattern
- Excel: metrics dashboard (test pass rate, coverage, task completion)
- Outlook: sends handoff emails on milestone completion
- Uses Microsoft Graph API (no desktop required)

### Layer 7 — Browser Task Execution
- Long-horizon tasks decomposed to atomic Playwright actions
- Each action is an MCP tool call: `browser.navigate`, `browser.click`, `browser.extract`
- Tasks in Airtable have a `browser_steps` field that defines the sequence
