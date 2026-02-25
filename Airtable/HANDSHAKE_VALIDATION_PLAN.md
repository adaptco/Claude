# E2E Handshake Validation and Repo Compaction: Two-PR Delivery Plan

**Status:** Non-mutating analysis — no code changes in this document.  
**Date:** Current phase  
**Scope:** Map handshake coverage, isolate multimodal timeout, define PR-1 and PR-2 deliverables  

---

## EXECUTIVE SUMMARY

### Current State (Ground Truth)
Your A2A digital twin implementation has:
- ✅ **Core modules implemented:**
  - `bootstrap_digital_twin.py` — entry point with RAG build, Airtable sync, tool testing
  - `digital_twin/twin_registry.py` — state management (files, agents, tasks, CI)
  - `mcp_extensions/claude_code_mcp_server.py` — 7 MCP tools (read/write/search/run tests/git/status)
  - `integrations/airtable/task_schema.py` — Airtable API client + schema mapping
  - `integrations/perplexity/search_agent.py` — Hybrid repo RAG + Perplexity fallback
  - `rag/vertical_tensor_slice.py` — L2-normalized semantic search (NDP)

- ❌ **Test suites do NOT exist:**
  - `tests/test_webhook_handshake.py` — MISSING
  - `tests/test_runtime_bridge_contract.py` — MISSING
  - `tests/test_handshake_client.py` — MISSING
  - `tests/test_multimodal_rag_workflow.py` — MISSING
  - `Airtable/tests/` directory is **empty**

- ⚠️ **Handshake coverage: ZERO**
  - No DMN bridge logic currently implemented
  - No `/handshake/init` endpoint
  - No runtime assignment contract validation
  - No CI gating for handshake flow

### Multimodal Timeout Root Cause
The timeout mentioned in your requirements refers to **non-existent tests**. The real bottlenecks (when they run):
1. `build_embedding_store()` — embeds entire repo via OpenAI (or hash fallback)
2. `PerplexitySearchAgent._tool_fn()` — makes HTTP calls to Perplexity API (30s timeout)
3. `AirtableClient.list_tasks()` — syncs Airtable base (network I/O)

**Why tests time out:** They're not isolated; they import and execute long-running setup code.

---

## PART 1: HANDSHAKE FLOW ANALYSIS

### Missing Layer 1: Runtime Bridge Contract
**What should exist:** `schemas/runtime_bridge.py`
```python
# Pseudo-code — NOT in current repo
from dataclasses import dataclass
from typing import List

@dataclass
class DMNGlobalVariable:
    """One mapped environment variable or runtime state → DMN XML element"""
    name: str                    # DMN element name (e.g., "A2A_RUNTIME_ENGINE")
    value: str                   # actual value or redacted fingerprint
    source: str                  # "env" | "runtime" | "airtable"
    xml_path: str                # e.g., "/process/globalVariable[@id='runtime.engine']"
    is_sensitive: bool = False   # if True, value is sha256:<hash>

@dataclass
class RuntimeAssignmentV1:
    """Contract for runtime → DMN bridge"""
    task_id: str
    agent_id: str
    assigned_at: float
    dmn_global_variables: List[DMNGlobalVariable]
    dmn_global_variables_xml: str  # well-formed DMN XML snippet
    runtime_metadata: dict         # {avatar, rbac_role, worker_pool, ...}
```

**Current status:** Not in `Airtable/a2a-digital-twin/` codebase.

---

### Missing Layer 2: Webhook Handshake Endpoint
**What should exist:** `orchestrator/webhook.py` or similar
```python
# Pseudo-code — NOT in current repo
@app.post("/handshake/init")
async def handshake_init(payload: HandshakeInitRequest) -> dict:
    """
    1. Validate API key (401 if missing/invalid)
    2. Extract runtime environment and task metadata
    3. Generate DMN global variables (deterministic, lexicographically sorted)
    4. Emit both JSON and XML representations
    5. Return state_payload with runtime assignment
    """
    # Step 1: Auth
    api_key = request.headers.get("X-API-Key")
    if not validate_api_key(api_key):
        return {"error": "Unauthorized"}, 401
    
    # Step 2: Extract runtime
    runtime_vars = extract_runtime_env()
    dmn_vars = map_to_dmn_globals(runtime_vars)
    
    # Step 3: Generate XML
    dmn_xml = generate_dmn_xml(dmn_vars)
    
    # Step 4: Return artifact
    return {
        "state_payload": {
            "dmn_global_variables": dmn_vars,
            "dmn_global_variables_xml": dmn_xml,
            "runtime_assignment": RuntimeAssignmentV1(...),
            ...
        }
    }
```

**Current status:** Not in `bootstrap_digital_twin.py`.

---

### Missing Layer 3: Test Suite
**Location:** `Airtable/tests/` (currently empty)

#### `test_webhook_handshake.py` (112 lines target)
```python
# Pseudo-code — should test:
def test_handshake_auth_enforced():
    """POST /handshake/init without API key returns 401"""
    
def test_handshake_success_includes_dmn_variables():
    """Valid POST returns state_payload with dmn_global_variables list and XML"""
    
def test_dmn_variables_lexicographically_sorted():
    """Variables are ordered by name for deterministic assertions"""
    
def test_dmn_xml_well_formed():
    """dmn_global_variables_xml is parseable XML, not just string"""
    
def test_sensitive_values_redacted():
    """Env vars marked sensitive (API_KEY, DB_PASSWORD) are fingerprinted, not plaintext"""
    
def test_runtime_assignment_round_trip():
    """RuntimeAssignmentV1 can be serialized and deserialized without loss"""
```

**Current status:** Not in codebase.

---

#### `test_runtime_bridge_contract.py` (100+ lines target)
```python
# Pseudo-code — should test:
def test_dmn_global_variable_model_has_required_fields():
    """name, value, source, xml_path exist and are correct type"""
    
def test_runtime_assignment_includes_dmn_fields():
    """RuntimeAssignmentV1.dmn_global_variables is List[DMNGlobalVariable]"""
    
def test_mapping_file_is_valid_yaml():
    """specs/xml_normalization_map.yaml parses and has required keys"""
    
def test_required_mappings_exist():
    """
    Assertions for:
      - A2A_RUNTIME_ENGINE → runtime.engine
      - A2A_MCP_PROVIDER → mcp.provider
      - All orchestration env keys
    """
    
def test_xml_generation_idempotent():
    """Same input always produces same XML (no randomness, deterministic ordering)"""
```

**Current status:** Not in codebase.

---

#### `test_handshake_client.py` (80+ lines target)
```python
# Pseudo-code — integration test:
def test_client_handshake_success():
    """Client POSTs valid payload, receives state_payload with all required fields"""
    
def test_client_extracts_runtime_metadata():
    """Client parses runtime_assignment.runtime_metadata (avatar, rbac_role, etc.)"""
    
def test_client_parses_dmn_xml():
    """Client successfully parses dmn_global_variables_xml, validates structure"""
    
def test_client_handles_auth_failure():
    """Client raises HandshakeAuthError on 401, with expected message"""
```

**Current status:** Not in codebase.

---

#### `test_multimodal_rag_workflow.py` (150+ lines target)
```python
# Pseudo-code — E2E workflow (WITH MOCKING):
@pytest.fixture
def mock_embedding_store(tmp_path):
    """Fixture: mock embedding store (not real OpenAI calls)"""
    
def test_rag_embedding_indexing():
    """Mock RAG: index small corpus, retrieve top-k by score"""
    
def test_perplexity_search_agent_fallthrough():
    """
    Mock Perplexity: repo score < 0.72 triggers fallback
    (don't actually call Perplexity API)
    """
    
def test_airtable_sync_to_twin():
    """
    Mock Airtable: list tasks, update twin state
    (don't actually call Airtable API)
    """
    
def test_multimodal_workflow_end_to_end():
    """
    Orchestrate: query → RAG search → (maybe fallback) → twin update
    All mocked, completes under 10 seconds
    """
```

**Current status:** Not in codebase. **TIMEOUT ROOT CAUSE:** If this test were to run unmocked, it would:
1. Call OpenAI API to build embedding store (30-120s)
2. Call Perplexity API (15-30s each call)
3. Call Airtable API (5-10s)
4. Total: 60-160s, **exceeds typical CI timeout of 30s**

---

## PART 2: MISSING INFRASTRUCTURE

### Schemas / Config Files
**Missing:**
- `schemas/runtime_bridge.py` — DMNGlobalVariable, RuntimeAssignmentV1 models
- `specs/xml_normalization_map.yaml` — Environment key → DMN XML path mapping

**Example mapping:**
```yaml
dmn_global_variable_map:
  A2A_RUNTIME_ENGINE:
    dmn_name: "A2A_RUNTIME_ENGINE"
    xml_path: "/definitions/process/globalVariable[@id='runtime.engine']"
    source: "env"
    sensitive: false
  
  A2A_MCP_PROVIDER:
    dmn_name: "A2A_MCP_PROVIDER"
    xml_path: "/definitions/process/globalVariable[@id='mcp.provider']"
    source: "env"
    sensitive: false
  
  A2A_API_KEY:
    dmn_name: "A2A_API_KEY"
    xml_path: "/definitions/process/globalVariable[@id='api_key']"
    source: "env"
    sensitive: true         # → redact as sha256:<hash>
```

---

### Orchestrator Module
**Missing:**
- `orchestrator/webhook.py` — `/handshake/init` endpoint
- `orchestrator/__init__.py`

---

### Entry Point Integration
**Current `bootstrap_digital_twin.py`:**
```python
async def start_mcp_server() -> None:
    # ✅ Registers MCP tools
    # ✅ Loads embedding store
    # ❌ Does NOT serve /handshake/init endpoint
    # ❌ Does NOT emit DMN global variables
```

**What's missing:**
- FastMCP or FastAPI server that exposes `/handshake/init`
- Runtime environment extraction and DMN mapping
- API key validation

---

## PART 3: TIMEOUT ANALYSIS

### Current Bottlenecks (by module)

| Module | Function | Current Impl | Timeout Risk |
|--------|----------|--------------|--------------|
| `rag/vertical_tensor_slice.py` | `build_embedding_store()` | OpenAI API (with hash fallback) | 60-120s (real), 5s (mocked) |
| `integrations/perplexity/search_agent.py` | `search_perplexity()` | HTTP call (30s timeout) | 30s per call (real), <1s (mocked) |
| `integrations/airtable/task_schema.py` | `AirtableClient.list_tasks()` | HTTP call to Airtable | 10-20s (real), <1s (mocked) |
| `bootstrap_digital_twin.py` | `sync_airtable()` | Sequential calls to above | 30-50s (real), <5s (mocked) |

### Recommended Test Isolation Strategy
```
CI Stage: "handshake" (8 min budget)
├── test_webhook_handshake.py (fixtures: mock API key validator) → 30s
├── test_runtime_bridge_contract.py (fixtures: mock YAML loader) → 20s
├── test_handshake_client.py (fixtures: mock HTTP server) → 20s
└── test_multimodal_rag_workflow.py (fixtures: mock embeddings, Perplexity, Airtable) → 60s

Total: ~130s (well under 8 min = 480s budget)
```

---

## PART 4: TWO-PR DELIVERY PLAN

### PR-1: Handshake Validation Gate (Functional)

**Scope:**
1. Add `schemas/runtime_bridge.py` with DMNGlobalVariable, RuntimeAssignmentV1 dataclasses
2. Add `specs/xml_normalization_map.yaml` with environment → DMN mapping
3. Add `orchestrator/webhook.py` with `/handshake/init` endpoint (FastAPI or FastMCP)
4. Update `bootstrap_digital_twin.py` to expose handshake endpoint (merge into `start_mcp_server()` or new handler)
5. Create `Airtable/tests/` suite with 4 test modules:
   - `test_webhook_handshake.py` (112 lines)
   - `test_runtime_bridge_contract.py` (100 lines)
   - `test_handshake_client.py` (80 lines)
   - `test_multimodal_rag_workflow.py` (150 lines) — **with all I/O mocked**
6. Add `.github/workflows/handshake-gate.yml` — CI job with 8-minute timeout

**Files Changed:**
```
Airtable/
├── schemas/
│   └── runtime_bridge.py (NEW)
├── specs/
│   └── xml_normalization_map.yaml (NEW)
├── orchestrator/
│   ├── __init__.py (NEW)
│   └── webhook.py (NEW)
├── bootstrap_digital_twin.py (MODIFIED — add handshake export)
└── tests/
    ├── __init__.py (NEW)
    ├── test_webhook_handshake.py (NEW)
    ├── test_runtime_bridge_contract.py (NEW)
    ├── test_handshake_client.py (NEW)
    └── test_multimodal_rag_workflow.py (NEW)

.github/
└── workflows/
    └── handshake-gate.yml (NEW)
```

**PR-1 Acceptance Criteria:**
- ✅ All 4 test modules pass locally and in CI
- ✅ CI handshake job completes under 8 minutes
- ✅ No unrelated cleanup deletions in diff
- ✅ Handshake endpoint `/handshake/init` returns deterministic JSON + XML
- ✅ DMN variables sorted lexicographically (no flake)
- ✅ API key validation enforced (401 on missing key)
- ✅ Sensitive values fingerprinted (sha256), not plaintext

---

### PR-2: Repo Compaction / Cleanup (Non-Functional)

**Scope:**
1. Identify and remove tracked temporary artifacts:
   - `tmpclaude-*` files (if any exist)
   - `specs/tmpclaude-*` artifacts
   - Duplicate wrapper modules (if identified)
2. Verify `.gitignore` prevents reintroduction
3. Consolidate duplicate implementations (if any) into single canonical location
4. Ensure backward-compatible import paths

**Files Changed:**
```
(depends on cleanup findings)
Airtable/
├── [removed temporary files]
├── [consolidated duplicates]
└── [updated imports for compatibility]

(potentially)
.gitignore (updated if needed)
```

**PR-2 Acceptance Criteria:**
- ✅ Cleanup contains ONLY non-functional structural changes
- ✅ All imports remain backward-compatible
- ✅ Test suite still passes (no functional regression)
- ✅ Diff is focused (no spurious whitespace changes)

---

## PART 5: TEST FIXTURES AND MOCKING STRATEGY

### Mock Layers (for `test_multimodal_rag_workflow.py`)

```python
# ✅ DO mock these (prevent external calls):
@pytest.fixture
def mock_embedding_store(tmp_path):
    """Create small (10-chunk) fake embedding store in temp dir"""
    keys = ["file1.py:0", "file2.md:0", ...]
    vectors = np.random.randn(10, 1536)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)  # L2-norm
    np.savez_compressed(tmp_path / "store.npz", keys=keys, vectors=vectors, ...)
    return tmp_path / "store.npz"

@pytest.fixture
def mock_perplexity_api(monkeypatch):
    """Patch httpx.AsyncClient to return deterministic Perplexity responses"""
    async def mock_post(*args, **kwargs):
        class MockResp:
            def raise_for_status(self): pass
            def json(self):
                return {
                    "choices": [{"message": {"content": "Mocked answer"}}],
                    "citations": ["https://example.com/doc1"],
                }
        return MockResp()
    
    monkeypatch.setattr("httpx.AsyncClient.post", mock_post)

@pytest.fixture
def mock_airtable_api(monkeypatch):
    """Patch AirtableClient to return deterministic task list"""
    async def mock_list_tasks(*args, **kwargs):
        return [
            AirtableTask(record_id="rec1", name="Task 1", status=TaskStatus.READY, ...),
            AirtableTask(record_id="rec2", name="Task 2", status=TaskStatus.BACKLOG, ...),
        ]
    
    monkeypatch.setattr("integrations.airtable.task_schema.AirtableClient.list_tasks", mock_list_tasks)

# ❌ DO NOT mock these (too low-level, test contract integrity):
# - DMN variable model creation (test the structure)
# - XML generation (test well-formedness)
# - Environment variable extraction (test mapping correctness)
```

---

## PART 6: CI GATING AND TIMEOUT BUDGET

### Handshake CI Job (`.github/workflows/handshake-gate.yml`)

```yaml
name: Handshake Validation Gate

on: [push, pull_request]

jobs:
  handshake:
    runs-on: ubuntu-latest
    timeout-minutes: 8  # Total budget: 480 seconds
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python 3.11
        uses: actions/setup-python@v4
        with:
          python-version: "3.11"
      
      - name: Install dependencies
        run: |
          pip install -e Airtable/
          pip install -r Airtable/requirements.txt
          pip install pytest pytest-cov pytest-timeout
      
      - name: Run Handshake Validation Suite
        run: |
          cd Airtable
          pytest tests/test_webhook_handshake.py \
                 tests/test_runtime_bridge_contract.py \
                 tests/test_handshake_client.py \
                 tests/test_multimodal_rag_workflow.py \
                 -v --tb=short --timeout=30 --timeout-method=thread
        env:
          # Use mocked APIs, not real ones
          OPENAI_API_KEY: "test-key-not-used"
          PERPLEXITY_API_KEY: "test-key-not-used"
          AIRTABLE_API_KEY: "test-key-not-used"
      
      - name: Report Coverage
        run: |
          pytest tests/ --cov=Airtable --cov-report=xml
      
      - name: Upload Coverage
        uses: codecov/codecov-action@v3
```

---

## PART 7: DECISION MATRIX

| Decision | Option A | Option B | Recommended |
|----------|----------|----------|-------------|
| **Test location** | `Airtable/tests/` | Parent `tests/` | **A** — stays with digital twin module |
| **Mock strategy** | Mock all I/O | Skip multimodal test | **A** — catches integration paths |
| **Timeout per test** | 30s | 60s | **30s** — strict to catch hangs |
| **DMN variable ordering** | Lexicographic | By insertion order | **Lexicographic** — deterministic, testable |
| **Sensitive redaction** | sha256 hash | Asterisks | **sha256** — preserves uniqueness, auditable |
| **CI budget** | 8 min | 15 min | **8 min** — aggressive, but achievable with mocks |
| **PR split** | One PR | Two PRs | **Two PRs** — reduces review scope |

---

## PART 8: OPEN DECISIONS FOR YOU

1. **DMN XML format:** Should handshake return raw BPMN 2.0 XML, or a simplified schema?
   - Current assumption: Raw BPMN XML (fully compatible with process engines)
   - Alternative: Simplified JSON-LD or custom schema

2. **Runtime metadata fields:** What fields belong in `RuntimeAssignmentV1.runtime_metadata`?
   - Current assumption: `{avatar, rbac_role, worker_pool, ...}`
   - Need confirmation of required fields

3. **Sensitive env var list:** Which env vars are sensitive and should be redacted?
   - Current assumption: `*_API_KEY, *_PASSWORD, *_SECRET, *_TOKEN`
   - Needs hardcoding or configuration

4. **Webhook endpoint location:** Should `/handshake/init` live in:
   - New `orchestrator/webhook.py` module?
   - Extended `bootstrap_digital_twin.py` (MCP server)?
   - Separate FastAPI app?

5. **CI matrix:** Should handshake gate also run on:
   - Only PR creation / commits to main?
   - Every commit (including branches)?
   - Scheduled nightly builds?

---

## PART 9: ROLLOUT CHECKLIST

- [ ] **Pre-PR-1:** Confirm decisions 1-5 in Part 8
- [ ] **PR-1 Drafting:**
  - [ ] Create `schemas/runtime_bridge.py`
  - [ ] Create `specs/xml_normalization_map.yaml`
  - [ ] Create `orchestrator/webhook.py` with `/handshake/init` endpoint
  - [ ] Create `Airtable/tests/` test suite (4 files, all mocked)
  - [ ] Create `.github/workflows/handshake-gate.yml`
  - [ ] Update `bootstrap_digital_twin.py` to export handshake handler
- [ ] **PR-1 Validation:**
  - [ ] `pnpm install` (or `pip install`) succeeds
  - [ ] `pytest Airtable/tests/ -v` passes locally
  - [ ] CI workflow completes under 8 minutes
  - [ ] Diff review: no cleanup code, only handshake additions
- [ ] **PR-1 Merge:** Require handshake gate green
- [ ] **PR-2 Drafting:** Identify and isolate cleanup changes
- [ ] **PR-2 Validation:** Smoke test + import checks
- [ ] **PR-2 Merge:** Follow PR-1

---

## APPENDIX: ESTIMATED LINE COUNTS

```
schemas/runtime_bridge.py           ~80 lines (3 dataclasses)
specs/xml_normalization_map.yaml    ~40 lines (YAML mapping)
orchestrator/__init__.py             ~5 lines (empty)
orchestrator/webhook.py             ~100 lines (endpoint + helpers)
tests/test_webhook_handshake.py     ~112 lines (6 test functions)
tests/test_runtime_bridge_contract.py ~100 lines (5 test functions)
tests/test_handshake_client.py       ~80 lines (4 test functions)
tests/test_multimodal_rag_workflow.py ~150 lines (5 test functions + fixtures)
.github/workflows/handshake-gate.yml ~50 lines (CI job)
bootstrap_digital_twin.py (delta)    ~30 lines (add handshake export)

TOTAL NEW: ~747 lines
TOTAL MODIFIED: ~30 lines (in 1 file)
```

---

## CONCLUSION

This plan delivers:
1. **Production-ready handshake flow** with deterministic DMN outputs and enforced auth
2. **Comprehensive test coverage** with mocked I/O (no external API calls in CI)
3. **CI gating** under 8-minute budget
4. **Two-PR split** that isolates functional changes (PR-1) from cleanup (PR-2)
5. **Clear decision points** for your review before implementation

**Next step:** Confirm or adjust the 5 open decisions in Part 8, then I'll implement PR-1.
