# Quick Reference: Claude Release Orchestrator Refactor

**Lock phrase**: `Canonical truth, attested and replayable.`

---

## TL;DR

Your workflow is **docker-compose → GKE ready**. Three new jobs added:

| Old | New |
|-----|-----|
| `wait-for-claude` | ✅ Same |
| `validate-and-check-conflicts` | ✅ Enhanced (+ hashing) |
| ➕ `generate-kompose-manifests` | Kompose → K8s + Kustomize |
| `bot-review-and-state` | ✅ Enhanced (+ Gate Receipt RFC8785) |
| ➕ `build-and-push-images` | Docker build → GCR push |
| ➕ `deploy-to-gke` | kubectl apply to GKE |

---

## Files You Got

| File | Purpose |
|------|---------|
| `CLAUDE_RELEASE_ORCHESTRATOR_ANALYSIS.md` | Full technical analysis |
| `CLAUDE_RELEASE_ORCHESTRATOR_REFACTORED.yml` | New workflow (copy this) |
| `UNIFIED_DIFF.patch` | git-applyable patch (git apply command) |
| `PR_DIFF_GUIDE.md` | Step-by-step application guide |
| `DELIVERABLES_SUMMARY.md` | This summary + next steps |
| `QUICK_REFERENCE.md` | This file |

---

## Apply in 3 Steps

### 1. Backup + Replace

```bash
cd /path/to/ADAPTCO-MAIN/A2A_MCP

# Backup current
cp .github/workflows/claude_release_orchestrator.yml \
   .github/workflows/claude_release_orchestrator.yml.backup

# Option A: Copy new file
cp CLAUDE_RELEASE_ORCHESTRATOR_REFACTORED.yml \
   .github/workflows/claude_release_orchestrator.yml

# Option B: Apply patch
git apply UNIFIED_DIFF.patch
```

### 2. Configure Secrets

Go to GitHub repo → Settings → Secrets → New:

| Secret | Value | Required? |
|--------|-------|-----------|
| `GCR_SA_KEY` | GCP service account JSON | ✅ For image push |
| `GCP_PROJECT` | Your GCP project ID | ✅ For image push |
| `GKE_CLUSTER` | Your GKE cluster name | ⚠️ Optional (for GKE deploy) |
| `GKE_ZONE` | Your GKE zone | ⚠️ Optional (for GKE deploy) |

**Get `GCR_SA_KEY`**:
```bash
gcloud iam service-accounts keys create key.json \
  --iam-account=ci-sa@my-project.iam.gserviceaccount.com
cat key.json | pbcopy  # macOS / or xclip on Linux
# Paste into GitHub secret
```

### 3. Commit & Push

```bash
git add .github/workflows/claude_release_orchestrator.yml
git commit -m "gate: add deterministic Gate Receipt + GKE deployment

- emit RFC8785 canonical JSON + sha256 bundle hash
- generate Kompose manifests + Kustomize overlays
- add docker build + GCR push step
- add optional GKE deployment job

Seal phrase: Canonical truth, attested and replayable.
Assisted-By: gordon"

git push origin feature/gke-deterministic-gates
# Create PR on GitHub
```

---

## Test Locally (Optional)

```bash
# Validate docker-compose
docker-compose -f docker-compose.unified.yml config > /dev/null

# Test kompose conversion
curl -L https://github.com/kubernetes/kompose/releases/download/v1.28.0/kompose-linux-amd64 -o kompose
chmod +x kompose
./kompose convert -f docker-compose.unified.yml -o /tmp/k8s-base/ --out yaml

# Validate K8s manifests
kubectl apply --dry-run=client -f /tmp/k8s-base/

# Test kustomize overlays
kustomize build k8s/overlays/dev/ | kubectl apply --dry-run=client -f -
kustomize build k8s/overlays/prod/ | kubectl apply --dry-run=client -f -
```

---

## Trigger Workflow

### Manual (Recommended)

1. Go to: GitHub repo → Actions → Claude Release Orchestrator
2. Click "Run workflow"
3. Fill in (optional):
   - `todo_issue_number`: your release issue (e.g., `42`)
   - `pr_number`: your PR (e.g., `123`)
   - `claude_task_complete`: `true` to skip TODO parsing
4. Click "Run workflow"

### What Happens

1. ✅ `wait-for-claude` — Gate on TODO completion
2. ✅ `validate-and-check-conflicts` — Run pytest + check merge conflicts
3. ✅ `generate-kompose-manifests` — Convert docker-compose → K8s
4. ✅ `bot-review-and-state` — Build Gate Receipt + post PR comment
5. ✅ `build-and-push-images` — Build + push Docker images to GCR
6. ✅ `deploy-to-gke` — Deploy to GKE (if secrets configured)

---

## Artifacts Generated

| Artifact | Contents |
|----------|----------|
| `system-state-{N}` | system_state.json + release docs |
| `gate-receipt-{N}` | RFC8785 canonical Gate Receipt |
| `k8s-manifests-{N}` | K8s base + overlays (dev/prod) |
| `docker-images-{N}` | Docker image TARs |
| `gate-receipt-final-{N}` | Gate Receipt + deployment confirmation |

**Download**:
```bash
gh run download <RUN_ID> -D ./artifacts/
ls -la artifacts/
```

---

## Example Gate Receipt (RFC8785)

```json
{
  "gate_receipt_version": "v1.0",
  "run_id": "1234567890",
  "run_number": "5",
  "commit_sha": "abc1234567890def",
  "timestamp": "2024-01-15T14:23:45.123456Z",
  "bundle_sha256": "5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03",
  "gates": {
    "claude_complete": "true",
    "tests_passed": "true",
    "conflicts_resolved": "true",
    "kompose_validated": true
  },
  "verdict": "PASSED",
  "failure_code": null,
  "seal_phrase": "Canonical truth, attested and replayable."
}
```

---

## Failure Codes

| Code | Meaning | Action |
|------|---------|--------|
| `CLAUDE_INCOMPLETE` | TODO checklist not done | Stop at `wait-for-claude` |
| `TESTS_FAILED` | pytest failed | Stop at `validate-and-check-conflicts` |
| `MERGE_CONFLICT` | Conflicts with main | Stop at `validate-and-check-conflicts` |
| `KOMPOSE_FAILED` | docker-compose invalid | Stop at `generate-kompose-manifests` |
| `IMAGE_PUSH_FAILED` | GCR push failed | Stop at `build-and-push-images` |
| `GKE_DEPLOY_FAILED` | kubectl apply failed | Stop at `deploy-to-gke` |

All failures are **fail-closed**: no partial state.

---

## Key Improvements

| Feature | Before | After |
|---------|--------|-------|
| **Gate Receipt** | ❌ JSON only | ✅ RFC8785 canonical + sha256 |
| **K8s Ready** | ❌ No | ✅ Kompose + Kustomize |
| **Image Registry** | ❌ Local | ✅ GCR push + SHA tagging |
| **GKE Deploy** | ❌ No | ✅ kubectl rollout |
| **Determinism** | ❌ No | ✅ Canonical JSON + hashes |
| **Audit Trail** | ⚠️ Partial | ✅ Full with seal phrase |

---

## Troubleshooting

### Missing GCR_SA_KEY

```bash
# Create service account key
gcloud iam service-accounts create ci-sa
gcloud iam service-accounts keys create key.json \
  --iam-account=ci-sa@my-project.iam.gserviceaccount.com
# Add to GitHub secret
```

### kompose convert fails

```bash
# Validate docker-compose
docker-compose -f docker-compose.unified.yml config

# Check for missing `image:` or `build:` directives
grep -n "image:\|build:" docker-compose.unified.yml
```

### pytest fails

```bash
# Run locally
pytest -v tests/test_release_orchestrator.py tests/test_mcp_agents.py

# Check imports
python -c "from orchestrator.release_orchestrator import ReleaseOrchestrator"
```

### kubectl apply fails

```bash
# Debug manifest
kustomize build k8s/overlays/prod/ -o /tmp/debug.yaml
kubectl apply --dry-run=client -f /tmp/debug.yaml -v 10
```

---

## Rollback

If you need to revert:

```bash
# Use backup
cp .github/workflows/claude_release_orchestrator.yml.backup \
   .github/workflows/claude_release_orchestrator.yml

# Or reset to main
git checkout main -- .github/workflows/claude_release_orchestrator.yml

# Commit
git add .github/workflows/claude_release_orchestrator.yml
git commit -m "revert: restore claude_release_orchestrator.yml"
```

---

## Next

1. **Apply workflow** (3 steps above)
2. **Configure secrets** (GCR_SA_KEY at minimum)
3. **Test locally** (optional but recommended)
4. **Trigger workflow** (manual via GitHub Actions)
5. **Review artifacts** (Gate Receipt, K8s manifests)
6. **Deploy to GKE** (optional, via deploy-to-gke job)

---

**Lock phrase**: `Canonical truth, attested and replayable.`  
**Questions?** See `DELIVERABLES_SUMMARY.md` or `PR_DIFF_GUIDE.md`  
**Assisted-By**: gordon
