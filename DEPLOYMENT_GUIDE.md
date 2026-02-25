# Deployment Pipeline Guide

## Overview

This deployment pipeline provides end-to-end CI/CD for the Control Plane application using GitHub Actions, Docker, and Kubernetes.

## Pipeline Stages

### 1. Test & Lint (`test.yml`)

**Triggers:** Push to main/develop, Pull Requests

Runs on matrix: Python 3.11, 3.12

Steps:
- Checkout code
- Install dependencies
- Run test suite (`pytest tests/test_harness.py`)
- Run linting (`pylint`)
- Upload coverage to Codecov

**Success criteria:**
- All 21 tests pass
- No pylint errors
- Coverage >80%

---

### 2. Build & Push Docker Image (`docker-build-push.yml`)

**Triggers:** Push to main, tags (v*), manual workflow dispatch

Features:
- Multi-stage Docker build with BuildKit cache
- Push to GitHub Container Registry (ghcr.io)
- Automatic image tagging (branch/tag/SHA)
- Trivy vulnerability scanning
- Results uploaded to GitHub Security

**Image tags generated:**
```
${REGISTRY_ORG}/${IMAGE_NAME}:main
${REGISTRY_ORG}/${IMAGE_NAME}:v1.0.0
${REGISTRY_ORG}/${IMAGE_NAME}:sha-abc123...
```

**Security scans:**
- Trivy scans for CVEs
- SARIF results available in Security tab

---

### 3. Deploy to Kubernetes (`deploy.yml`)

**Triggers:** Tag creation (v*), manual workflow dispatch with environment selection

**Workflow:**
1. Extract image tag (from git tag or commit SHA)
2. Configure kubectl with KUBE_CONFIG secret
3. Update deployment image
4. Wait for rollout to complete
5. Verify pods are healthy
6. Send Slack notification

**Environment-specific:**
- Staging: Automatic for main branch merges
- Production: Manual trigger (requires approval)

**Example deployment:**
```bash
# Manual trigger via GitHub UI
# Environment: production
# Deploys version from git tag to k8s cluster
```

---

## Local Deployment

### Option 1: Docker Compose (Development/Staging)

```bash
# Staging with live reload
docker compose -f docker-compose.staging.yaml up -d

# Check status
docker compose -f docker-compose.staging.yaml ps
docker compose -f docker-compose.staging.yaml logs control-plane-proxy -f
```

### Option 2: Docker Compose (Production)

```bash
# Create .env.prod from template
cp .env.prod.example .env.prod
# Edit .env.prod with real credentials

# Production deployment
docker compose -f docker-compose.prod.yaml up -d

# Verify
docker compose -f docker-compose.prod.yaml ps
```

### Option 3: Kubernetes

```bash
# Create namespace
kubectl create namespace control-plane

# Apply configurations
kubectl apply -f k8s/rbac.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/extras.yaml

# Verify deployment
kubectl get deployment -n control-plane
kubectl get pods -n control-plane

# Port forward for testing
kubectl port-forward -n control-plane svc/control-plane-proxy 8080:80

# View logs
kubectl logs -n control-plane -l app=control-plane-proxy -f
```

---

## Secrets & Credentials

### GitHub Secrets Required

For CI/CD to work, add these secrets to your GitHub repository:

1. **GITHUB_TOKEN** - Auto-provided by GitHub Actions
2. **KUBE_CONFIG** - Base64-encoded kubeconfig file
   ```bash
   cat ~/.kube/config | base64 | xclip
   # Add as KUBE_CONFIG secret
   ```
3. **SLACK_WEBHOOK** - (Optional) For deployment notifications
   ```
   https://hooks.slack.com/services/T00000000/B00000000/XXXX
   ```

### Database & Redis Passwords

Production deployments require secure credential management:

```bash
# Option 1: GitHub Secrets (simple)
# Add DB_PASSWORD, REDIS_PASSWORD secrets

# Option 2: Kubernetes Secrets (recommended)
kubectl create secret generic control-plane-secrets \
  --from-literal=DB_PASSWORD=$(openssl rand -base64 32) \
  --from-literal=REDIS_PASSWORD=$(openssl rand -base64 32) \
  -n control-plane
```

---

## Environment-Specific Configuration

### Staging

- Build from source (docker-compose.staging.yaml)
- Debug logging enabled
- Live code reload via volume mounts
- Prometheus metrics exposed
- Dev database credentials

**Start staging:**
```bash
docker compose -f docker-compose.staging.yaml up -d
curl http://localhost:8080/health
```

### Production

- Pull pre-built images from registry
- INFO logging only
- No live reload
- Database from secrets/vault
- Redis for session caching

**Start production:**
```bash
docker compose -f docker-compose.prod.yaml up -d
docker compose -f docker-compose.prod.yaml exec postgres \
  psql -U vvl -d vvl -f init-schema.sql
```

---

## Monitoring & Observability

### Health Checks

All deployments include health checks:

```bash
# Docker Compose
docker inspect control-plane-proxy | jq '.State.Health'

# Kubernetes
kubectl get pod -n control-plane <pod-name> -o jsonpath='{.status.conditions}'
```

### Logs

```bash
# Local
docker compose logs control-plane-proxy -f

# Kubernetes
kubectl logs -n control-plane -l app=control-plane-proxy -f
```

### Metrics (Optional)

If Prometheus is enabled (staging):
```
http://localhost:9090
```

Query examples:
- `rate(http_requests_total[5m])` - Request rate
- `http_request_duration_seconds` - Request latency
- `up{job="control-plane-proxy"}` - Service health

---

## Troubleshooting

### Docker Build Failures

```bash
# Check Dockerfile syntax
docker build . --check

# Build with verbose output
docker build . --progress=plain

# Clean build cache
docker builder prune -a
```

### Kubernetes Deployment Issues

```bash
# Check pod events
kubectl describe pod -n control-plane <pod-name>

# Check logs
kubectl logs -n control-plane <pod-name>

# Rollback to previous version
kubectl rollout undo deployment/control-plane-proxy -n control-plane

# Check resource constraints
kubectl top nodes
kubectl top pods -n control-plane
```

### Database Connection Issues

```bash
# Test connection (local)
docker exec vvl-postgres psql -U vvl -d vvl -c "SELECT 1;"

# Test from app container
docker exec control-plane-proxy python -c \
  "import psycopg2; psycopg2.connect('postgresql://vvl:pass@postgres:5432/vvl')"
```

---

## Rollback Procedures

### Git-based Rollback

```bash
# Rollback via GitHub tag
git tag -d v1.0.0
git push origin :refs/tags/v1.0.0
git tag v1.0.0 <previous-commit-sha>
git push origin v1.0.0
# Redeploy via GitHub Actions
```

### Kubernetes Rollback

```bash
# List rollout history
kubectl rollout history deployment/control-plane-proxy -n control-plane

# Rollback to previous version
kubectl rollout undo deployment/control-plane-proxy -n control-plane

# Rollback to specific revision
kubectl rollout undo deployment/control-plane-proxy --to-revision=2 -n control-plane
```

### Docker Compose Rollback

```bash
# Modify docker-compose.prod.yaml image tag
# From: ${REGISTRY_ORG}/${IMAGE_NAME}:latest
# To:   ${REGISTRY_ORG}/${IMAGE_NAME}:v1.0.0

docker compose -f docker-compose.prod.yaml up -d
```

---

## Performance Tuning

### Resource Limits

Adjust in `k8s/deployment.yaml`:

```yaml
resources:
  requests:
    cpu: 250m      # Minimum guaranteed
    memory: 256Mi
  limits:
    cpu: 500m      # Maximum allowed
    memory: 512Mi
```

### Scaling

```bash
# Manual scaling
kubectl scale deployment/control-plane-proxy --replicas=5 -n control-plane

# HPA (Horizontal Pod Autoscaler) automatically scales based on:
- CPU: >70% → scale up
- Memory: >80% → scale up
- Min replicas: 3, Max: 10
```

### Build Cache Optimization

GitHub Actions uses layer caching. To optimize:

1. Order Dockerfile steps by frequency of change (least frequent first)
2. Pin dependency versions
3. Use `.dockerignore` to exclude unnecessary files

---

## Next Steps

1. **Configure secrets** - Add GitHub secrets and kubeconfig
2. **Set deployment placeholders** - Fill `${REGISTRY_ORG}`, `${IMAGE_NAME}`, `${VH2_DOMAIN}`, `${GITHUB_ORG}`, and `${ALLOWED_ORIGIN}`
3. **Test locally** - Run `docker-compose.staging.yaml` first
4. **Deploy to staging** - Verify in staging before production
5. **Enable monitoring** - Set up Prometheus/Grafana
6. **Document runbooks** - Add team-specific procedures

---

## References

- GitHub Actions: https://docs.github.com/actions
- Docker Build: https://docs.docker.com/build/concepts/overview/
- Kubernetes: https://kubernetes.io/docs/
- Docker Compose: https://docs.docker.com/compose/
