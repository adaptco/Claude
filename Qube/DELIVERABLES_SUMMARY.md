# Claude Release Orchestrator Refactor — Deliverables Summary

**Lock phrase**: `Canonical truth, attested and replayable.`

---

## What Was Done

I analyzed your **`claude_release_orchestrator.yml`** GitHub Actions workflow (from `ADAPTCO-MAIN/A2A_MCP/.github/workflows/`) and identified it as a **docker-compose-centric release gate** that works well for local CI but lacks several **GKE-critical features**:

### Problems Identified

1. ❌ **No deterministic Gate Receipt** — Current workflow uploads `system_state.json` but without RFC8785 canonicalization, sha256 hashing, or seal phrase
2. ❌ **No Kubernetes manifests** — docker-compose.unified.yml is not translated to K8s (no Kompose integration)
3. ❌ **No image registry integration** — No GCR push, no image tagging by commit SHA
4. ❌ **No GKE deployment job** — Cannot directly deploy to Kubernetes
5. ❌ **No fail-closed validation** — Implicit failures; no explicit failure codes or deterministic replay verification

### Solution Delivered

Three actionable artifacts:

---

## 📦 Deliverable 1: Analysis Document

**File**: `CLAUDE_RELEASE_ORCHESTRATOR_ANALYSIS.md`

**Contents**:
- Executive summary of current state vs. GKE requirements
- Detailed breakdown of docker-compose services (8 services, 7 ports)
- GKE compatibility gaps (Kompose, K8s resources, determinism)
- Recommended 4-phase refactor with code examples
- Failure modes + fail-closed behavior matrix
- Commit message convention

**Key Insights**:
- Your workflow gates on Claude TODO completion ✅
- pytest validation is present ✅
- But: no seal/bundle step before registry push
- No Kustomize overlays for multi-environment (dev/staging/prod)

---

## 📋 Deliverable 2: Refactored Workflow

**File**: `CLAUDE_RELEASE_ORCHESTRATOR_REFACTORED.yml`

**New Jobs** (5 total):

| Job | Purpose | Status |
|-----|---------|--------|
| `wait-for-claude` | Gate on Claude TODO completion | **Existing** (unchanged) |
| `validate-and-check-conflicts` | Run pytest + detect merge conflicts | **Existing** (enhanced) |
| `generate-kompose-manifests` | **NEW** — Convert docker-compose → K8s + Kustomize |
| `bot-review-and-state` | Build deterministic Gate Receipt + PR comment | **Existing** (enhanced) |
| `build-and-push-images` | **NEW** — Docker build + GCR push |
| `deploy-to-gke` | **NEW** (optional) — Apply to GKE + confirm |

**New Features**:

1. **Deterministic Gate Receipt (RFC8785 JCS)**
   - Canonical JSON with sorted keys
   - sha256 hash of sealed bundle
   - Dependency fingerprints (requirements.txt, docker-compose.yml)
   - Explicit `verdict` + `failure_code`
   - Seal phrase: `Canonical truth, attested and replayable.`

2. **Kompose → Kustomize Pipeline**
   - Generates K8s base manifests from docker-compose.unified.yml
   - Creates `k8s/overlays/dev/` (1 replica) and `k8s/overlays/prod/` (3+ replicas)
   - Validates all manifests with `kubectl apply --dry-run=client`

3. **Docker Image Build + GCR Push**
   - Builds `orchestrator`, `rbac-gateway`, `ingest-api` images
   - Tags by commit SHA (deterministic)
   - Pushes to GCR (Google Container Registry)

4. **GKE Deployment (Optional)**
   - Pulls K8s manifests from artifact
   - Injects pushed image digests
   - Applies with `kubectl apply -k k8s/overlays/prod/`
   - Checks rollout status

---

## 📖 Deliverable 3: PR Diff Guide

**File**: `PR_DIFF_GUIDE.md`

**Contents**:
- Step-by-step instructions to apply the refactored workflow
- GitHub secrets configuration checklist (GCR_SA_KEY, GCP_PROJECT, GKE_CLUSTER, GKE_ZONE)
- Local testing commands (kompose, kustomize, kubectl, docker build)
- Workflow trigger instructions (manual vs. push-based)
- Expected artifact outputs (Gate Receipt, K8s manifests, Docker images)
- Sample Gate Receipt JSON (RFC8785 canonical format)
- Troubleshooting (missing secrets, kompose failures, pytest failures)
- Rollback instructions

**Key Steps**:
1. Create new branch: `feature/gke-deterministic-gates`
2. Replace workflow file with refactored version
3. Configure GitHub secrets
4. Test locally (optional)
5. Trigger workflow manually to verify
6. Merge to main

---

## 🔍 Key Technical Changes

### 1. Dependency Hashing

```yaml
- name: Compute dependency hashes
  id: hashes
  run: |
    echo "requirements_hash=$(sha256sum requirements.txt | cut -d' ' -f1)" >> $GITHUB_OUTPUT
    echo "compose_hash=$(sha256sum docker-compose.unified.yml | cut -d' ' -f1)" >> $GITHUB_OUTPUT
```

**Purpose**: Ensures reproducibility; changes to requirements or compose file trigger re-validation.

### 2. Kompose Conversion

```bash
./kompose convert -f docker-compose.unified.yml -o k8s/base/ --out yaml
kubectl apply --dry-run=client -f k8s/base/  # Validate
```

**Purpose**: Translates docker-compose services → K8s Deployment/StatefulSet/Service/PVC.

### 3. Kustomize Overlays

```yaml
# k8s/overlays/dev/kustomization.yaml
bases:
  - ../../base
replicas:
  - name: orchestrator
    count: 1
commonLabels:
  environment: dev
```

**Purpose**: Multi-environment support (dev/staging/prod) without duplicating manifests.

### 4. RFC8785 Canonical JSON

```python
canonical_json = json.dumps(state, sort_keys=True, separators=(',', ':'))
bundle_sha256 = hashlib.sha256(canonical_json.encode()).hexdigest()
```

**Purpose**: Deterministic JSON serialization; same input → same hash, enabling reproducible builds and verification.

### 5. Gate Receipt with Seal Phrase

```json
{
  "verdict": "PASSED",
  "failure_code": null,
  "seal_phrase": "Canonical truth, attested and replayable.",
  "bundle_sha256": "5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03"
}
```

**Purpose**: Cryptographic attestation of release readiness; enables audit trail + replay verification.

---

## 🎯 Governance Alignment

The refactor aligns with your **AGENTS.md** governance model:

| Constraint | How Refactor Honors It |
|-----------|----------------------|
| **Bifurcation Invariant** | Lane A (client) is consume-only; Lane B (orchestrator) produces + seals artifacts |
| **Determinism** | RFC8785 JCS + sha256 hashing of canonical bytes |
| **Governance Lock Phrase** | `Canonical truth, attested and replayable.` embedded in Gate Receipt |
| **Fail-Closed** | Explicit failure codes; no partial state; gates stop on mismatch |
| **Audit Trail** | Gate Receipt persisted as artifact; reproducible hashes enable replay verification |

---

## 📊 What's Preserved

✅ **Existing behavior**:
- TODO checklist parsing (Issue → checked/total)
- pytest validation (orchestrator + agent tests)
- Merge conflict detection
- Bot PR comments with status
- Artifact uploads (system state, docs, specs)

✅ **No breaking changes**:
- Workflow still named `Claude Release Orchestrator`
- Inputs remain: `todo_issue_number`, `pr_number`, `claude_task_complete`
- Same trigger: `workflow_dispatch` (manual)

---

## 🚀 Next Steps (For You)

### Immediate (Today)

1. **Review the three documents**:
   - Read `CLAUDE_RELEASE_ORCHESTRATOR_ANALYSIS.md` for context
   - Skim `CLAUDE_RELEASE_ORCHESTRATOR_REFACTORED.yml` for new jobs
   - Follow `PR_DIFF_GUIDE.md` for step-by-step application

2. **Configure GitHub secrets** (if deploying to GCR/GKE):
   - Go to repo Settings → Secrets → Create `GCR_SA_KEY`, `GCP_PROJECT`
   - (Optional) Create `GKE_CLUSTER`, `GKE_ZONE` if using GKE deployment

3. **Test locally** (optional but recommended):
   ```bash
   cd /path/to/ADAPTCO-MAIN/A2A_MCP
   # Validate docker-compose.unified.yml
   docker-compose -f docker-compose.unified.yml config > /dev/null
   # Install kompose, test conversion
   curl -L https://github.com/kubernetes/kompose/releases/download/v1.28.0/kompose-linux-amd64 -o kompose
   chmod +x kompose
   ./kompose convert -f docker-compose.unified.yml -o /tmp/k8s-test/ --out yaml
   ```

### Short-Term (This Week)

4. **Create PR with refactored workflow**:
   ```bash
   git checkout -b feature/gke-deterministic-gates
   # Replace workflow file (follow PR_DIFF_GUIDE.md)
   git commit -m "gate: add deterministic Gate Receipt + GKE deployment"
   git push origin feature/gke-deterministic-gates
   # Create PR on GitHub
   ```

5. **Review generated artifacts**:
   - Gate Receipt (RFC8785 canonical JSON)
   - K8s manifests (base + overlays)
   - PR bot comment with status matrix

### Medium-Term (Next 2 Weeks)

6. **Merge to main** after code review
7. **Deploy to GKE** (optional):
   ```bash
   # Trigger workflow
   gh workflow run claude_release_orchestrator.yml -r main
   # Wait for build-and-push-images to complete
   # Manually run deploy-to-gke or add auto-trigger
   ```

8. **Monitor in production**:
   - Check `kubectl logs -l app=orchestrator`
   - Verify Gate Receipt in SSOT ledger

---

## 📋 Checklist for Application

Before merging this PR, verify:

- [ ] GitHub secrets configured (GCR_SA_KEY at minimum)
- [ ] `docker-compose.unified.yml` validates: `docker-compose -f docker-compose.unified.yml config`
- [ ] pytest passes: `pytest tests/test_release_orchestrator.py tests/test_mcp_agents.py`
- [ ] All required fields in Gate Receipt (verdict, failure_code, seal_phrase)
- [ ] Kustomize overlays generate valid K8s manifests
- [ ] Workflow YAML syntax is valid (no indentation errors)
- [ ] Commit message includes "Assisted-By: gordon" trailer
- [ ] Backup of original workflow created

---

## 📞 Support

If you hit issues:

1. **Kompose failures**: Check `docker-compose.unified.yml` for missing `image:` or `build:` directives
2. **pytest failures**: Run `pytest -v` locally; check for import/schema errors
3. **GCR push failures**: Verify service account key has Artifact Registry Writer role
4. **GKE deployment failures**: Check cluster credentials, namespace, and resource limits

All three deliverables include troubleshooting sections.

---

## 🎁 What You Get

✅ **Deterministic release pipeline** — Same input → same hash → reproducible builds  
✅ **GKE-ready infrastructure** — Kompose manifests + Kustomize overlays  
✅ **Audit trail** — Gate Receipt with cryptographic seal  
✅ **Fail-closed validation** — Explicit failure codes, no silent degradation  
✅ **Backwards compatible** — Existing workflow inputs and behavior preserved  

---

**Lock phrase**: `Canonical truth, attested and replayable.`  
**Assisted-By**: gordon  
**Date**: 2024

