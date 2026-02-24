# Prometheus Metrics for A2A Orchestrator

**Lock phrase**: `Canonical truth, attested and replayable.`

---

## Overview

The A2A MCP Orchestrator now exposes Prometheus metrics at `/metrics` without changing existing `/health` semantics or JSON shape.

This enables:
- Request rate monitoring
- Latency tracking (P50, P95, P99)
- System halt reason breakdown
- SLO/alerting foundation
- Later K8s/ArgoCD integration

---

## Metrics Exposed

### 1. Request Counter
```
a2a_orchestrator_requests_total{result="success|halt|error"}
```

**Type**: Counter  
**Labels**: 
- `result`: "success", "halt", or "error"

**Example output**:
```
a2a_orchestrator_requests_total{result="success"} 42.0
a2a_orchestrator_requests_total{result="halt"} 5.0
a2a_orchestrator_requests_total{result="error"} 2.0
```

**What it tracks**: Total number of orchestrator requests by outcome.

---

### 2. Plan Ingress Counter
```
a2a_orchestrator_plan_ingress_total{status="created|resumed|error"}
```

**Type**: Counter  
**Labels**:
- `status`: "created", "resumed", or "error"

**Example output**:
```
a2a_orchestrator_plan_ingress_total{status="created"} 12.0
a2a_orchestrator_plan_ingress_total{status="resumed"} 8.0
a2a_orchestrator_plan_ingress_total{status="error"} 1.0
```

**What it tracks**: Plan ingress events (new vs. resumed).

---

### 3. Verification Results Counter
```
a2a_orchestrator_verification_results_total{valid="true|false"}
```

**Type**: Counter  
**Labels**:
- `valid`: "true" or "false"

**Example output**:
```
a2a_orchestrator_verification_results_total{valid="true"} 35.0
a2a_orchestrator_verification_results_total{valid="false"} 4.0
```

**What it tracks**: Verification outcome breakdown.

---

### 4. System Halt Breakdown
```
a2a_orchestrator_system_halt_total{reason="missing_fields|out_of_range|invalid_schema|timeout|exception"}
```

**Type**: Counter  
**Labels**:
- `reason`: halt reason (e.g., "missing_fields", "out_of_range", etc.)

**Example output**:
```
a2a_orchestrator_system_halt_total{reason="missing_fields"} 3.0
a2a_orchestrator_system_halt_total{reason="out_of_range"} 2.0
a2a_orchestrator_system_halt_total{reason="exception"} 0.0
```

**What it tracks**: Why requests were halted (diagnostic breakdown).

---

### 5. Duration Histogram (Latency)
```
a2a_orchestrator_duration_ms{le="10|25|50|100|250|500|1000|2000|5000|+Inf", result="success|halt|error"}
a2a_orchestrator_duration_ms_sum{result="success|halt|error"}
a2a_orchestrator_duration_ms_count{result="success|halt|error"}
```

**Type**: Histogram  
**Labels**:
- `result`: "success", "halt", or "error"
- `le`: bucket threshold (in milliseconds)

**Example output**:
```
# Latency buckets (how many requests completed within X ms)
a2a_orchestrator_duration_ms_bucket{le="10",result="success"} 5.0
a2a_orchestrator_duration_ms_bucket{le="50",result="success"} 18.0
a2a_orchestrator_duration_ms_bucket{le="100",result="success"} 32.0
a2a_orchestrator_duration_ms_bucket{le="+Inf",result="success"} 42.0

# Total time spent (for computing average)
a2a_orchestrator_duration_ms_sum{result="success"} 2850.5
a2a_orchestrator_duration_ms_count{result="success"} 42.0
```

**What it tracks**: Operation latency by outcome (enables SLO/alert thresholds).

---

## Accessing Metrics

### Local Testing

```bash
# Start the application
cd /path/to/A2A_MCP
uvicorn orchestrator.webhook:app --host 0.0.0.0 --port 8000

# In another terminal, fetch metrics
curl -s http://localhost:8000/metrics
```

**Expected response**:
```
# HELP a2a_orchestrator_requests_total Total orchestrator requests by result type
# TYPE a2a_orchestrator_requests_total counter
a2a_orchestrator_requests_total{result="success"} 10.0
a2a_orchestrator_requests_total{result="halt"} 2.0
a2a_orchestrator_requests_total{result="error"} 0.0

# HELP a2a_orchestrator_duration_ms Orchestrator operation latency in milliseconds
# TYPE a2a_orchestrator_duration_ms histogram
...
```

### In Kubernetes

Once deployed to GKE, configure Prometheus scraping:

**1. ServiceMonitor** (if using Prometheus Operator):
```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: a2a-orchestrator
spec:
  selector:
    matchLabels:
      app: orchestrator
  endpoints:
    - port: metrics
      interval: 30s
      path: /metrics
```

**2. Prometheus scrape config** (if self-hosted):
```yaml
scrape_configs:
  - job_name: 'a2a-orchestrator'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_label_app]
        action: keep
        regex: orchestrator
      - source_labels: [__meta_kubernetes_pod_port_name]
        action: keep
        regex: metrics
```

---

## Usage Examples

### Record a Successful Request

```python
from orchestrator.metrics import record_request

duration_ms = 150.5
record_request(result='success', duration_ms=duration_ms)
```

This increments:
- `a2a_orchestrator_requests_total{result="success"}`
- Histogram bucket for `a2a_orchestrator_duration_ms{result="success"}`

### Record a Halt with Reason

```python
from orchestrator.metrics import record_request

duration_ms = 75.2
halt_reason = 'missing_fields'
record_request(result='halt', duration_ms=duration_ms, halt_reason=halt_reason)
```

This increments:
- `a2a_orchestrator_requests_total{result="halt"}`
- `a2a_orchestrator_system_halt_total{reason="missing_fields"}`
- Histogram bucket for `a2a_orchestrator_duration_ms{result="halt"}`

### Record Plan Ingress

```python
from orchestrator.metrics import record_plan_ingress

record_plan_ingress('created')  # New plan
# or
record_plan_ingress('resumed')  # Existing plan resumed
```

### Record Verification Result

```python
from orchestrator.metrics import record_verification

verification_passed = True
record_verification(valid=verification_passed)
```

---

## Prometheus Query Examples

### Request Rate (per second)
```promql
rate(a2a_orchestrator_requests_total[5m])
```

### Success Rate
```promql
rate(a2a_orchestrator_requests_total{result="success"}[5m]) /
rate(a2a_orchestrator_requests_total[5m])
```

### P95 Latency
```promql
histogram_quantile(0.95, rate(a2a_orchestrator_duration_ms_bucket[5m]))
```

### Halt Breakdown
```promql
a2a_orchestrator_system_halt_total
```

### Verification Pass Rate
```promql
rate(a2a_orchestrator_verification_results_total{valid="true"}[5m]) /
rate(a2a_orchestrator_verification_results_total[5m])
```

---

## Integration with Existing Code

The metrics are **opt-in** via explicit `record_*()` calls. Existing endpoints and JSON contracts are unchanged:

✅ **`/health`** — Same JSON response (no changes)  
✅ **`/orchestrate`** — Same request/response contract  
✅ **`/plans/ingress`** — Same behavior, added metrics recording  
✅ **`/metrics`** — New endpoint, Prometheus exposition format

---

## Testing Metrics Locally

### 1. Generate Some Requests

```bash
# Generate successful request
curl -X POST http://localhost:8000/orchestrate \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "user_query=test"

# Generate plan ingress (creates new plan)
curl -X POST http://localhost:8000/plans/ingress \
  -H "Content-Type: application/json" \
  -d '{"plan_id": "test-plan-1"}'

# Resume same plan
curl -X POST http://localhost:8000/plans/ingress \
  -H "Content-Type: application/json" \
  -d '{"plan_id": "test-plan-1"}'
```

### 2. Fetch Metrics

```bash
curl -s http://localhost:8000/metrics | grep a2a_orchestrator
```

**Expected output**:
```
a2a_orchestrator_requests_total{result="success"} 2.0
a2a_orchestrator_plan_ingress_total{status="created"} 1.0
a2a_orchestrator_plan_ingress_total{status="resumed"} 1.0
a2a_orchestrator_duration_ms_bucket{le="10",result="success"} 0.0
a2a_orchestrator_duration_ms_bucket{le="50",result="success"} 2.0
...
```

---

## Architecture Notes

- **No external middleware**: Metrics are recorded directly in handler functions via explicit `record_*()` calls
- **Prometheus-native format**: Uses `prometheus-client` library for standard exposition
- **Per-operation tracking**: Latency recorded per request (enables histogram quantiles)
- **Fail-closed validation**: All metrics are counters/histograms (no shared mutable state)

---

## Next Steps

### Local Development
1. ✅ Metrics module created (`orchestrator/metrics.py`)
2. ✅ Webhook updated with metric recording (`orchestrator/webhook.py`)
3. ✅ `/metrics` endpoint added
4. Test locally: `curl http://localhost:8000/metrics`

### Kubernetes Integration (Later)
1. Deploy A2A to GKE (existing K8s manifests)
2. Add ServiceMonitor or Prometheus scrape config (points to `/metrics`)
3. Set up Grafana dashboards
4. Configure alerts (e.g., halt rate > 10%, latency p95 > 500ms)

---

## Reference

- **Prometheus Client Library**: https://github.com/prometheus/client_python
- **Exposition Format**: https://github.com/prometheus/docs/blob/main/content/docs/instrumenting/exposition_formats.md
- **PromQL Queries**: https://prometheus.io/docs/prometheus/latest/querying/basics/

---

**Lock phrase**: `Canonical truth, attested and replayable.`
