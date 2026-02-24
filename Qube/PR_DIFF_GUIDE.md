# PR Diff Guide: Claude Release Orchestrator Refactor

**Lock phrase**: `Canonical truth, attested and replayable.`

---

## Summary of Changes

This refactor upgrades the GitHub Actions workflow from a **docker-compose-centric release gate** to a **deterministic, Kubernetes-ready CI/CD pipeline** with:

1. ✅ **Deterministic Gate Receipt** (RFC8785 JCS + sha256 hash + seal phrase)
2. ✅ **docker-compose → Kompose → Kustomize** translation layer
3. ✅ **Docker image build + GCR push** (with image tagging by commit SHA)
4. ✅ **GKE deployment job** (optional, triggered on main + manual workflow_dispatch)
5. ✅ **Fail-closed validation** (explicit failure codes, no silent degradation)

---

## Step-by-Step Application

### 1. Create New Branch

```bash
cd /path/to/ADAPTCO-MAIN/A2A_MCP
git checkout -b feature/gke-deterministic-gates
```

### 2. Back Up Current Workflow

```bash
cp .github/workflows/claude_release_orchestrator.yml \
   .github/workflows/claude_release_orchestrator.yml.backup
```

### 3. Apply the Refactored Workflow

Replace the current workflow with the refactored version:

```bash
cat > .github/workflows/claude_release_orchestrator.yml <<'EOF'
[PASTE THE FULL CONTENT OF CLAUDE_RELEASE_ORCHESTRATOR_REFACTORED.yml HERE]
EOF
```

Or manually:
1. Open `.github/workflows/claude_release_orchestrator.yml`
2. Replace the entire file with the contents of `CLAUDE_RELEASE_ORCHESTRATOR_REFACTORED.yml`

### 4. Create `.github/workflows/claude_release_orchestrator.yml.backup`

For safety, add the backup to `.gitignore`:

```bash
echo ".github/workflows/*.backup" >> .gitignore
```

### 5. Verify Structure

```bash
# Check syntax (requires github CLI or manual inspection)
ls -lh .github/workflows/claude_release_orchestrator.yml
wc -l .github/workflows/claude_release_orchestrator.yml
```

### 6. Stage and Commit

```bash
git add .github/workflows/claude_release_orchestrator.yml .gitignore
git commit -m "gate: add deterministic Gate Receipt + GKE deployment

- emit RFC8785 canonical JSON + sha256 bundle hash
- generate Kompose manifests + Kustomize overlays (dev/prod)
- add docker build + GCR push step
- add optional GKE deployment job with rollout status check
- integrate fail-closed validation gates + explicit failure codes

Seal phrase: Canonical truth, attested and replayable.
Assisted-By: gordon"
```

---

## Pre-Deployment Checklist

### ✅ GitHub Secrets Configuration

Before running the workflow, configure these secrets in GitHub:

1. **`GCR_SA_KEY`** or **`GCP_SA_KEY`**
   - Value: JSON service account key (Google Cloud)
   - Permissions needed: Artifact Registry Writer, GKE Developer
   - Get it from:
     ```bash
     gcloud iam service-accounts keys create key.json \
       --iam-account=your-sa@your-project.iam.gserviceaccount.com
     cat key.json | pbcopy  # macOS
     # or
     cat key.json | xclip -selection clipboard  # Linux
     ```
   - Go to: GitHub repo → Settings → Secrets and variables → Actions → New repository secret
   - Name: `GCR_SA_KEY`
   - Paste the JSON

2. **`GCP_PROJECT`**
   - Value: your GCP project ID (e.g., `my-project-12345`)
   - Go to: GitHub repo → Settings → Secrets and variables → Actions → New repository secret
   - Name: `GCP_PROJECT`
   - Paste the project ID

3. **`GKE_CLUSTER`** (optional, for GKE deployment)
   - Value: your GKE cluster name (e.g., `a2a-prod-cluster`)
   - Only needed if you plan to use the `deploy-to-gke` job

4. **`GKE_ZONE`** (optional, for GKE deployment)
   - Value: your GKE cluster zone (e.g., `us-central1-a`)
   - Only needed if you plan to use the `deploy-to-gke` job

### ✅ Local Testing (Optional)

Before pushing to main, test locally:

```bash
# 1. Install kompose
curl -L https://github.com/kubernetes/kompose/releases/download/v1.28.0/kompose-linux-amd64 -o kompose
chmod +x kompose

# 2. Generate K8s manifests from docker-compose.unified.yml
./kompose convert -f docker-compose.unified.yml -o k8s/base/ --out yaml

# 3. Validate manifests (requires kubectl installed)
kubectl apply --dry-run=client -f k8s/base/

# 4. Build Kustomize overlays
mkdir -p k8s/overlays/dev k8s/overlays/prod
kustomize build k8s/overlays/dev/ | kubectl apply --dry-run=client -f -
kustomize build k8s/overlays/prod/ | kubectl apply --dry-run=client -f -

# 5. Inspect generated manifests
ls -la k8s/base/
ls -la k8s/overlays/
```

### ✅ Docker Build Test

```bash
# Test building each service locally
docker build -t test-orchestrator:latest .
docker build -t test-rbac-gateway:latest ./rbac
docker build -t test-ingest-api:latest ./pipeline/ingest_api

# Verify images
docker images | grep test-
```

---

## Triggering the Workflow

### Method 1: Manual Trigger (Recommended for Testing)

1. Go to: GitHub repo → Actions → Claude Release Orchestrator
2. Click "Run workflow"
3. Provide optional inputs:
   - `todo_issue_number`: (e.g., `42`)
   - `pr_number`: (e.g., `123`)
   - `claude_task_complete`: (set to `true` to bypass TODO parsing)
4. Click "Run workflow"

### Method 2: On Push (if configured)

Add an `on:` trigger to the workflow (optional):

```yaml
on:
  workflow_dispatch: ...
  push:
    branches:
      - main
    paths:
      - 'requirements.txt'
      - 'docker-compose.unified.yml'
      - 'Dockerfile'
      - 'orchestrator/**'
```

---

## Artifact Outputs

After a successful workflow run, GitHub will generate these artifacts:

| Artifact | Contents |
|----------|----------|
| `system-state-{run_number}` | system_state.json + release docs + specs |
| `gate-receipt-{run_number}` | Deterministic Gate Receipt (RFC8785 JCS) |
| `k8s-manifests-{run_number}` | Generated K8s base + overlays (dev/prod) |
| `docker-images-{run_number}` | Docker image TAR files (optional) |
| `gate-receipt-final-{run_number}` | Gate Receipt + deployment confirmation |

**Download artifacts**:

```bash
gh run download <RUN_ID> -D ./artifacts/
ls -la artifacts/
```

---

## Expected Gate Receipt (RFC8785 Canonical)

```json
{
  "gate_receipt_version": "v1.0",
  "run_id": "1234567890",
  "run_number": "5",
  "commit_sha": "abc1234567890def",
  "branch": "refs/heads/main",
  "workflow_ref": "ADAPTCO-MAIN/A2A_MCP/.github/workflows/claude_release_orchestrator.yml@refs/heads/main",
  "timestamp": "2024-01-15T14:23:45.123456Z",
  "runtime_matrix": {
    "python_version": "3.11",
    "runner": "ubuntu-latest"
  },
  "dependency_fingerprint": {
    "requirements_txt_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "docker_compose_unified_hash": "d4735fea8e8d6135f07b72ded27f08b2a7c5f5f5"
  },
  "bundle_sha256": "5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03",
  "schema_versions": {
    "system_state": "v1.0",
    "gate_receipt": "v1.0"
  },
  "gates": {
    "claude_complete": "true",
    "tests_passed": "true",
    "conflicts_resolved": "true",
    "kompose_validated": true
  },
  "verdict": "PASSED",
  "failure_code": null,
  "seal_phrase": "Canonical truth, attested and replayable.",
  "system_state": { ... }
}
```

---

## Troubleshooting

### Issue: `GCR_SA_KEY` not found

**Cause**: GitHub secret not configured.

**Fix**:
```bash
# Create service account key (GCP)
gcloud iam service-accounts keys create key.json \
  --iam-account=ci-sa@my-project.iam.gserviceaccount.com

# Add to GitHub
cat key.json | pbcopy
# Go to Settings → Secrets → New repository secret → GCR_SA_KEY → Paste
```

### Issue: `kompose convert` fails

**Cause**: Invalid docker-compose.unified.yml syntax.

**Fix**:
```bash
# Validate compose file
docker-compose -f docker-compose.unified.yml config > /dev/null

# Check for service issues
docker-compose -f docker-compose.unified.yml ps --services
```

### Issue: Kustomize validation fails

**Cause**: Base manifests have invalid references or schema issues.

**Fix**:
```bash
# Debug Kustomize build
kustomize build k8s/overlays/dev/ -o /tmp/debug.yaml
kubectl apply --dry-run=client -f /tmp/debug.yaml -v 10
```

### Issue: `pytest` tests fail

**Cause**: test_release_orchestrator.py or test_mcp_agents.py have failures.

**Fix**:
```bash
# Run locally
pytest -v tests/test_release_orchestrator.py tests/test_mcp_agents.py

# Check for missing imports or schema changes
python -m py_compile orchestrator/release_orchestrator.py
```

---

## Reverting the Change

If you need to roll back:

```bash
# Option 1: Restore from backup
cp .github/workflows/claude_release_orchestrator.yml.backup \
   .github/workflows/claude_release_orchestrator.yml

# Option 2: Reset to main
git checkout main -- .github/workflows/claude_release_orchestrator.yml

# Commit
git add .github/workflows/claude_release_orchestrator.yml
git commit -m "revert: restore claude_release_orchestrator.yml to pre-refactor state"
```

---

## Summary of Benefits

| Feature | Before | After |
|---------|--------|-------|
| **Gate Receipt** | ❌ JSON only | ✅ RFC8785 canonical + sha256 hash |
| **K8s Manifests** | ❌ Manual | ✅ Kompose-generated + Kustomize overlays |
| **Image Registry** | ❌ Local only | ✅ GCR push + tagged by SHA |
| **GKE Deployment** | ❌ None | ✅ kubectl apply + rollout status |
| **Fail-Closed** | ⚠️ Partial | ✅ Explicit failure codes + determinism |
| **Determinism** | ❌ No | ✅ Canonical JSON + reproducible hashes |

---

## Next Steps

1. **Merge this PR** to `main`
2. **Configure GitHub secrets** (GCR_SA_KEY, GCP_PROJECT, GKE_CLUSTER, GKE_ZONE)
3. **Run workflow manually** to verify all gates pass
4. **Review artifacts** (Gate Receipt, K8s manifests)
5. **Deploy to GKE** (optional, via `deploy-to-gke` job or manual kubectl)

---

**Lock phrase**: `Canonical truth, attested and replayable.`  
**Assisted-By**: gordon
