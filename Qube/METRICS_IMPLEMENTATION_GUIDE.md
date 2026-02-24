# Add Prometheus Metrics to A2A Orchestrator

**Commit Message**:
```
feat: add prometheus metrics endpoint for orchestrator observability

- add prometheus-client dependency (prom-client)
- create orchestrator/metrics.py with:
  - request counter (result="success|halt|error")
  - plan ingress counter (status="created|resumed|error")
  - verification counter (valid="true|false")
  - system halt breakdown (reason="...")
  - duration histogram (latency in milliseconds)
- integrate metrics recording in webhook.py:
  - /plans/ingress (plan_ingress_total + duration + record_request)
  - /orchestrate (record_request with duration)
- add /metrics endpoint (Prometheus exposition format)
- preserve /health JSON contract (unchanged)

Metrics accessible at: GET /metrics (text/plain, Prometheus format)
No middleware or health frameworks; direct prometheus-client integration.

Assisted-By: gordon
```

---

## Files Changed

### 1. `requirements.txt`
**Add line**: `prometheus-client`

### 2. `orchestrator/metrics.py` (NEW)
- Counter: `a2a_orchestrator_requests_total{result="..."}`
- Counter: `a2a_orchestrator_plan_ingress_total{status="..."}`
- Counter: `a2a_orchestrator_verification_results_total{valid="..."}`
- Counter: `a2a_orchestrator_system_halt_total{reason="..."}`
- Histogram: `a2a_orchestrator_duration_ms{result="..."}`
- Utility functions: `record_request()`, `record_plan_ingress()`, `record_verification()`

### 3. `orchestrator/webhook.py`
**Modified**:
- Added imports: `time`, `Response`, `prometheus_client`
- Updated `_plan_ingress_impl()`: added metrics recording (created/resumed/error)
- Updated `/orchestrate`: added request timing + metrics recording
- Added `/health`: existing health check (unchanged JSON)
- **Added `/metrics`**: Prometheus endpoint (NEW)

---

## Testing After Merge

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the app
uvicorn orchestrator.webhook:app --host 0.0.0.0 --port 8000

# 3. Generate some requests
curl -X POST http://localhost:8000/orchestrate \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "user_query=test"

# 4. Fetch metrics
curl -s http://localhost:8000/metrics | head -30

# Expected output:
# TYPE a2a_orchestrator_requests_total counter
# HELP a2a_orchestrator_requests_total Total orchestrator requests by result type
# a2a_orchestrator_requests_total{result="success"} 1.0
```

---

## Integration Points

### Within A2A (No Changes to Contracts)
- ✅ `/health` — Unchanged
- ✅ `/orchestrate` — Same request/response
- ✅ `/plans/ingress` — Same behavior, metrics added

### Later K8s Work
- Expose port 8000 in K8s Service
- Add Prometheus scrape config or ServiceMonitor
- Query `/metrics` endpoint for latency/error rates
- Build Grafana dashboards

---

## Minimal & Production-Ready

- **No frameworks**: Direct `prometheus-client` usage
- **No middleware**: Explicit metric recording in handlers
- **No state sharing**: All counters/histograms are thread-safe
- **Standard format**: Prometheus exposition format (text/0.0.4)

---

**Lock phrase**: `Canonical truth, attested and replayable.`
