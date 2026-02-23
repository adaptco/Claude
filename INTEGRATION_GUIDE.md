# Integration Guide: Control Plane ↔ Music Video System

**Bridging avatar.controlbus.synthetic.engineer.v1 with music-video-generator.jsx and cici-music-studio-v11.json**

---

## Overview

This guide explains how to integrate the constitutional wrapper (control plane) with the existing music video generation system **without modifying the existing code**.

The integration acts as a transparent proxy that:
1. Intercepts requests to the music video system
2. Applies ByteSampler determinism
3. Enforces constitutional constraints
4. Logs everything to VVL
5. Passes through to original system

---

## Architecture Layers

```
┌─────────────────────────────────────────────────────────┐
│ User Interface (Browser)                                │
│ - music-video-generator.jsx (React)                    │
└─────────────────────────────────────────────────────────┘
                        ↓ HTTP/WebSocket
┌─────────────────────────────────────────────────────────┐
│ Control Plane Proxy (NEW)                               │
│ - Port 8080                                             │
│ - ByteSampler adapter                                   │
│ - Constitutional enforcer                               │
│ - VVL logger                                            │
└─────────────────────────────────────────────────────────┘
                        ↓ HTTP
┌─────────────────────────────────────────────────────────┐
│ Original Backend (UNCHANGED)                            │
│ - Port 8000                                             │
│ - music-video-generator backend                         │
│ - cici-music-studio MCP client                          │
└─────────────────────────────────────────────────────────┘
```

---

## Step 1: Deploy Control Plane Proxy

### Proxy Server (Python FastAPI)

```python
"""
control_plane_proxy.py

Transparent proxy that wraps music video generation with ByteSampler + VVL.
"""

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import httpx
import hashlib
from typing import Dict, Any
import json

from bytesampler_adapter import ByteSamplerAdapter
from vvl import VersionedVectorLedger
from constitutional import ConstitutionalEnforcer

app = FastAPI(title="avatar.controlbus.synthetic.engineer.v1 Proxy")

# Initialize components
bytesampler = ByteSamplerAdapter(
    model_endpoint="https://api.mistral.ai/v1",
    tokenizer_type="bpe"
)
vvl = VersionedVectorLedger(db_path="./vvl.db")
constitutional = ConstitutionalEnforcer()

# Backend URL (original music video system)
BACKEND_URL = "http://localhost:8000"


@app.post("/api/upload-music")
async def upload_music(file: UploadFile = File(...)):
    """
    Intercept music file upload, apply constitutional checks, log to VVL.
    """
    # Read file
    file_bytes = await file.read()
    file_hash = "sha256:" + hashlib.sha256(file_bytes).hexdigest()
    
    # Initialize session
    session = vvl.create_session({
        "input_file_hash": file_hash,
        "rng_seed": bytesampler.current_seed
    })
    
    # Constitutional check: File format and size
    validation = constitutional.validate_file_upload(
        filename=file.filename,
        size_bytes=len(file_bytes)
    )
    
    if not validation.passed:
        # REFUSE: Log refusal event
        vvl.append({
            "entry_type": "refusal",
            "session_id": session.session_id,
            "refusal": {
                "reason": "file_validation_failed",
                "constraint_violated": validation.constraint,
                "requested": {
                    "filename": file.filename,
                    "size_bytes": len(file_bytes)
                },
                "suggested_fix": validation.message
            }
        })
        
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Constitutional constraint violated",
                "reason": validation.message,
                "vvl_entry_id": vvl.latest_entry_id
            }
        )
    
    # COMMIT: Pass through to backend
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BACKEND_URL}/api/upload-music",
            files={"file": (file.filename, file_bytes, file.content_type)}
        )
    
    backend_result = response.json()
    
    # Log to VVL
    vvl.append({
        "entry_type": "music_analysis",
        "session_id": session.session_id,
        "bytesampler_state": {
            "byte_prefix": file_bytes[:1024].hex(),
            "rng_seed": bytesampler.current_seed
        },
        "wrapped_system_input": {
            "agent": "musicAnalyzer",
            "parameters": {
                "file_hash": file_hash,
                "filename": file.filename
            }
        },
        "wrapped_system_output": {
            "result": backend_result,
            "execution_time_ms": response.elapsed.total_seconds() * 1000
        },
        "constitutional_checks": [validation.to_dict()]
    })
    
    # Return enhanced response with session info
    return JSONResponse({
        **backend_result,
        "session_id": session.session_id,
        "vvl_entry_id": vvl.latest_entry_id
    })


@app.post("/api/generate-scene")
async def generate_scene(scene_params: Dict[str, Any]):
    """
    Intercept scene generation, enforce C5 symmetry, log to VVL.
    """
    session_id = scene_params.get("session_id")
    
    # ByteSampler: Sample deterministic control sequence
    params_bytes = json.dumps(scene_params, sort_keys=True).encode()
    control_bytes = bytesampler.sample_next_bytes(
        params_bytes,
        max_length=1024
    )
    
    # Constitutional check: C5 symmetry
    validation = constitutional.validate_c5_symmetry(
        element_count=scene_params.get("element_count", 0)
    )
    
    if not validation.passed:
        # REFUSE
        vvl.append({
            "entry_type": "refusal",
            "session_id": session_id,
            "refusal": {
                "reason": "c5_symmetry_violation",
                "constraint_violated": "c5_symmetry",
                "requested": scene_params,
                "deviation": validation.deviation,
                "suggested_fix": f"Adjust element count to nearest multiple of 5"
            },
            "bytesampler_state": {
                "byte_prefix": params_bytes.hex(),
                "control_bytes": control_bytes.hex(),
                "rng_seed": bytesampler.current_seed
            }
        })
        
        raise HTTPException(
            status_code=400,
            detail={
                "error": "C5 symmetry violation",
                "element_count": scene_params.get("element_count"),
                "deviation": validation.deviation,
                "suggested_fix": validation.message
            }
        )
    
    # COMMIT: Pass through to backend
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BACKEND_URL}/api/generate-scene",
            json=scene_params
        )
    
    backend_result = response.json()
    
    # Log to VVL
    vvl.append({
        "entry_type": "scene_generation",
        "session_id": session_id,
        "bytesampler_state": {
            "byte_prefix": params_bytes.hex(),
            "control_bytes": control_bytes.hex(),
            "rng_seed": bytesampler.current_seed
        },
        "wrapped_system_input": {
            "agent": "sceneComposer",
            "parameters": scene_params
        },
        "wrapped_system_output": {
            "result": backend_result
        },
        "constitutional_checks": [validation.to_dict()]
    })
    
    return JSONResponse({
        **backend_result,
        "vvl_entry_id": vvl.latest_entry_id
    })


@app.post("/api/mcp/invoke")
async def invoke_mcp_tool(request: Dict[str, Any]):
    """
    Intercept MCP tool invocations, wrap with ByteSampler determinism.
    """
    tool_name = request.get("tool_name")
    parameters = request.get("parameters", {})
    session_id = request.get("session_id")
    
    # ByteSampler: Sample control sequence
    params_bytes = json.dumps(parameters, sort_keys=True).encode()
    control_bytes = bytesampler.sample_next_bytes(params_bytes)
    
    # Pass through to MCP backend
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BACKEND_URL}/api/mcp/invoke",
            json=request
        )
    
    backend_result = response.json()
    
    # Log to VVL
    vvl.append({
        "entry_type": f"mcp_{tool_name}",
        "session_id": session_id,
        "bytesampler_state": {
            "byte_prefix": params_bytes.hex(),
            "control_bytes": control_bytes.hex(),
            "rng_seed": bytesampler.current_seed
        },
        "wrapped_system_input": {
            "agent": tool_name,
            "parameters": parameters
        },
        "wrapped_system_output": {
            "result": backend_result
        }
    })
    
    return JSONResponse({
        **backend_result,
        "vvl_entry_id": vvl.latest_entry_id
    })


@app.get("/api/vvl/session/{session_id}")
async def get_vvl_session(session_id: str):
    """
    Retrieve VVL entries for a session (for replay).
    """
    entries = vvl.get_session_entries(session_id)
    return JSONResponse({
        "session_id": session_id,
        "entry_count": len(entries),
        "entries": [e.to_dict() for e in entries]
    })


@app.post("/api/vvl/replay/{session_id}")
async def replay_session(session_id: str):
    """
    Replay a complete session for verification.
    """
    from replay import ReplayEngine
    
    replay_engine = ReplayEngine(vvl, bytesampler, BACKEND_URL)
    result = await replay_engine.replay_session(session_id)
    
    return JSONResponse(result.to_dict())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
```

---

## Step 2: Update Frontend Configuration

### Minimal Change to music-video-generator.jsx

The React component needs **one line changed** - the API endpoint URL:

```javascript
// OLD:
const API_BASE = 'http://localhost:8000';

// NEW:
const API_BASE = 'http://localhost:8080';  // Point to control plane proxy
```

**That's it!** The entire constitutional wrapper is now in the request path.

---

## Step 3: VVL Database Schema

### PostgreSQL Schema

```sql
-- sessions table
CREATE TABLE sessions (
    session_id UUID PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ,
    initial_seed BIGINT NOT NULL,
    status VARCHAR(20) NOT NULL,
    entry_count INT DEFAULT 0,
    refusal_count INT DEFAULT 0,
    head_hash TEXT,
    input_file_hash TEXT,
    output_video_hash TEXT,
    metadata JSONB
);

-- vvl_entries table
CREATE TABLE vvl_entries (
    entry_id UUID PRIMARY KEY,
    session_id UUID REFERENCES sessions(session_id),
    entry_type VARCHAR(50) NOT NULL,
    timestamp_ns BIGINT NOT NULL,
    prev_hash TEXT,
    current_hash TEXT NOT NULL,
    bytesampler_state JSONB NOT NULL,
    wrapped_system_input JSONB,
    wrapped_system_output JSONB,
    constitutional_checks JSONB,
    refusal JSONB,
    branch_metadata JSONB,
    user_id TEXT
);

-- Indexes for efficient queries
CREATE INDEX idx_vvl_entries_session ON vvl_entries(session_id);
CREATE INDEX idx_vvl_entries_timestamp ON vvl_entries(timestamp_ns);
CREATE INDEX idx_vvl_entries_type ON vvl_entries(entry_type);
CREATE INDEX idx_vvl_entries_hash ON vvl_entries(current_hash);

-- Replay verification table
CREATE TABLE replay_results (
    replay_id UUID PRIMARY KEY,
    session_id UUID REFERENCES sessions(session_id),
    replay_timestamp TIMESTAMPTZ NOT NULL,
    total_entries INT NOT NULL,
    verified_entries INT NOT NULL,
    divergences INT NOT NULL,
    divergence_details JSONB,
    replay_duration_ms FLOAT
);
```

---

## Step 4: Constitutional Enforcer Implementation

```python
"""
constitutional.py

Enforcement of constitutional constraints.
"""

from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result of a constitutional validation check"""
    passed: bool
    constraint: str
    deviation: float = 0.0
    message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "constraint": self.constraint,
            "passed": self.passed,
            "deviation": self.deviation,
            "message": self.message
        }


class ConstitutionalEnforcer:
    """Enforces constitutional constraints on music video generation"""
    
    def __init__(self):
        self.config = {
            "c5_symmetry": {
                "enabled": True,
                "tolerance": 0.1,
                "max_elements": 60
            },
            "file_upload": {
                "max_size_mb": 100,
                "allowed_formats": ["mp3", "wav", "ogg", "flac"]
            },
            "budget": {
                "max_tokens": 100000,
                "max_gpu_seconds": 300
            }
        }
    
    def validate_c5_symmetry(self, element_count: int) -> ValidationResult:
        """Validate C5 symmetry constraint"""
        if not self.config["c5_symmetry"]["enabled"]:
            return ValidationResult(passed=True, constraint="c5_symmetry")
        
        # Check divisibility by 5
        remainder = element_count % 5
        if remainder != 0:
            return ValidationResult(
                passed=False,
                constraint="c5_symmetry",
                deviation=remainder,
                message=f"Element count {element_count} not divisible by 5. "
                       f"Adjust to {element_count - remainder} or {element_count + (5 - remainder)}."
            )
        
        # Check max elements
        max_elements = self.config["c5_symmetry"]["max_elements"]
        if element_count > max_elements:
            return ValidationResult(
                passed=False,
                constraint="scene_complexity",
                deviation=element_count - max_elements,
                message=f"Element count {element_count} exceeds maximum {max_elements}."
            )
        
        return ValidationResult(
            passed=True,
            constraint="c5_symmetry",
            message=f"Element count {element_count} valid (C5 symmetry)"
        )
    
    def validate_file_upload(self, filename: str, size_bytes: int) -> ValidationResult:
        """Validate uploaded file"""
        # Check file extension
        ext = filename.split('.')[-1].lower()
        allowed = self.config["file_upload"]["allowed_formats"]
        
        if ext not in allowed:
            return ValidationResult(
                passed=False,
                constraint="file_format",
                message=f"Format '{ext}' not allowed. Use: {', '.join(allowed)}"
            )
        
        # Check file size
        max_size = self.config["file_upload"]["max_size_mb"] * 1024 * 1024
        if size_bytes > max_size:
            return ValidationResult(
                passed=False,
                constraint="file_size",
                deviation=(size_bytes - max_size) / 1024 / 1024,
                message=f"File size {size_bytes / 1024 / 1024:.1f}MB exceeds "
                       f"maximum {max_size / 1024 / 1024}MB"
            )
        
        return ValidationResult(
            passed=True,
            constraint="file_upload",
            message=f"File '{filename}' valid"
        )
    
    def validate_budget(self, tokens_used: int, gpu_seconds: float) -> ValidationResult:
        """Validate resource budget"""
        if tokens_used > self.config["budget"]["max_tokens"]:
            return ValidationResult(
                passed=False,
                constraint="budget_tokens",
                deviation=tokens_used - self.config["budget"]["max_tokens"],
                message=f"Token budget exceeded: {tokens_used} > {self.config['budget']['max_tokens']}"
            )
        
        if gpu_seconds > self.config["budget"]["max_gpu_seconds"]:
            return ValidationResult(
                passed=False,
                constraint="budget_gpu",
                deviation=gpu_seconds - self.config["budget"]["max_gpu_seconds"],
                message=f"GPU time exceeded: {gpu_seconds}s > {self.config['budget']['max_gpu_seconds']}s"
            )
        
        return ValidationResult(
            passed=True,
            constraint="budget",
            message="Within budget"
        )
```

---

## Step 5: Deployment Checklist

### Development Environment

- [ ] Install dependencies: `pip install fastapi uvicorn httpx`
- [ ] Set up PostgreSQL database
- [ ] Run migrations: `psql < schema.sql`
- [ ] Start backend: `python backend.py` (port 8000)
- [ ] Start control plane: `python control_plane_proxy.py` (port 8080)
- [ ] Update frontend: Change API_BASE to `:8080`
- [ ] Test file upload → Should log to VVL
- [ ] Test scene generation → Should enforce C5 symmetry
- [ ] Test refusal → Should get 400 with clear error

### Production Environment

- [ ] Deploy control plane as Kubernetes service
- [ ] Configure PostgreSQL with TimescaleDB extension
- [ ] Set up monitoring for VVL append rate
- [ ] Configure alerts for constitutional violations
- [ ] Set up replay verification cron job (daily)
- [ ] Document operational procedures
- [ ] Train team on VVL debugging

---

## Step 6: Testing the Integration

### Test 1: Valid Scene Generation

```bash
curl -X POST http://localhost:8080/api/generate-scene \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "01937b3f-e4a2-7890-8f3c-123456789abc",
    "scene_type": "chorus",
    "element_count": 60,
    "bpm": 128
  }'
```

**Expected:** 200 OK with scene data + VVL entry ID

### Test 2: C5 Symmetry Violation

```bash
curl -X POST http://localhost:8080/api/generate-scene \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "01937b3f-e4a2-7890-8f3c-123456789abc",
    "scene_type": "verse",
    "element_count": 73
  }'
```

**Expected:** 400 Bad Request with refusal details

### Test 3: Replay Session

```bash
curl -X POST http://localhost:8080/api/vvl/replay/01937b3f-e4a2-7890-8f3c-123456789abc
```

**Expected:** Replay result with verification status

---

## Troubleshooting

### Issue: Frontend gets CORS errors

**Solution:** Add CORS middleware to control plane proxy:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Issue: VVL append is slow

**Solution:** Use batch inserts and connection pooling:

```python
# Use asyncpg for PostgreSQL
import asyncpg

pool = await asyncpg.create_pool(
    "postgresql://user:pass@localhost/vvl",
    min_size=5,
    max_size=20
)
```

### Issue: Replay divergence detected

**Solution:** Check:
1. Model checkpoint version matches
2. RNG seed was correctly restored
3. ByteSampler tokenizer type matches
4. No non-deterministic code in wrapped system

---

## Monitoring and Observability

### Metrics to Track

```python
from prometheus_client import Counter, Histogram

# Constitutional checks
constitutional_checks = Counter(
    'constitutional_checks_total',
    'Total constitutional checks',
    ['constraint', 'result']
)

# Refusals
refusals = Counter(
    'refusals_total',
    'Total refusal events',
    ['reason']
)

# VVL operations
vvl_appends = Counter('vvl_appends_total', 'Total VVL appends')
vvl_latency = Histogram('vvl_append_seconds', 'VVL append latency')

# ByteSampler
bytesampler_samples = Counter('bytesampler_samples_total', 'Total byte samples')
bytesampler_latency = Histogram('bytesampler_latency_seconds', 'ByteSampler latency')
```

### Dashboard Queries

```sql
-- Recent refusals
SELECT entry_type, refusal->>'reason', COUNT(*)
FROM vvl_entries
WHERE entry_type = 'refusal'
  AND timestamp_ns > extract(epoch from now() - interval '1 hour') * 1e9
GROUP BY entry_type, refusal->>'reason';

-- Session success rate
SELECT 
  COUNT(*) as total_sessions,
  SUM(CASE WHEN refusal_count = 0 THEN 1 ELSE 0 END) as successful,
  SUM(CASE WHEN refusal_count > 0 THEN 1 ELSE 0 END) as with_refusals
FROM sessions
WHERE created_at > now() - interval '24 hours';

-- Average ByteSampler overhead
SELECT 
  AVG((bytesampler_state->>'distribution_entropy')::float) as avg_entropy,
  COUNT(*) as sample_count
FROM vvl_entries
WHERE bytesampler_state IS NOT NULL;
```

---

## Next Steps

1. **Phase 1 (Week 1-2):** Deploy in permissive mode (log only, don't block)
2. **Phase 2 (Week 3-4):** Enable strict mode (fail-closed)
3. **Phase 3 (Week 5-6):** Add replay verification to CI/CD
4. **Phase 4 (Week 7-8):** Enable multi-model ensembles

## Summary

The control plane wraps the existing music video system **without any modifications** to the core generation logic. It operates as:

- **Entropy choke point** - All randomness flows through ByteSampler
- **Constitutional enforcer** - Invalid requests are refused at the boundary
- **Audit logger** - Complete VVL trail of all decisions
- **Replay engine** - Deterministic verification of past sessions

This preserves the creative behavior of music-video-generator.jsx while adding the guarantees needed for Sovereign OS integration.
