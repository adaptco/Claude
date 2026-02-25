# Deployment Pipeline - Quick Start

Your complete CI/CD pipeline is ready. Here's what's been created:

## 📁 Files Created

### GitHub Actions Workflows (`.github/workflows/`)
- **test.yml** - Run tests on PR/push to main/develop
- **docker-build-push.yml** - Build and push image to registry on merge to main
- **deploy.yml** - Deploy to Kubernetes on tag or manual trigger
- **build-reusable.yml** - Reusable workflow for consistency

### Docker Compose Files
- **docker-compose.staging.yaml** - Staging environment with live reload
- **docker-compose.prod.yaml** - Production environment with PostgreSQL & Redis
- **compose.dev.yaml** - Existing dev environment (already present)
- **compose.debug.yaml** - Existing debug environment (already present)

### Kubernetes Manifests (`k8s/`)
- **deployment.yaml** - Deployment, Service, ConfigMap, HPA, PDB
- **rbac.yaml** - ServiceAccount, Role, RoleBinding, NetworkPolicy
- **extras.yaml** - Namespace, CronJob, ServiceMonitor

### Configuration & Guides
- **Makefile** - Command shortcuts for all operations
- **DEPLOYMENT_GUIDE.md** - Complete deployment documentation
- **setup.sh** - Interactive setup script
- **.env.staging.example** - Staging environment template
- **.env.prod.example** - Production environment template

---

## 🚀 Quick Start (3 Steps)

### Step 1: Local Testing
```bash
make dev
make test
make lint
```

### Step 2: Staging Deployment
```bash
cp .env.staging.example .env.staging
# Edit .env.staging with your values
make staging
```

### Step 3: Production (via GitHub)
```bash
# Tag your code
git tag v1.0.0
git push origin v1.0.0

# GitHub Actions automatically:
# 1. Runs tests
# 2. Builds Docker image
# 3. Pushes to registry
# 4. Deploys to Kubernetes
```

---

## 📋 Pipeline Stages

```
Push to main
    ↓
Test & Lint (Python 3.11, 3.12)
    ↓
Build Docker Image (multi-platform)
    ↓
Push to ghcr.io
    ↓
Scan for CVEs (Trivy)
    ↓
Deploy to Kubernetes (staging/production)
    ↓
Run health checks
    ↓
Slack notification
```

---

## 🔑 Required GitHub Secrets

1. **KUBE_CONFIG** - Base64-encoded kubeconfig
   ```bash
   cat ~/.kube/config | base64 | pbcopy  # macOS
   cat ~/.kube/config | base64 | xclip   # Linux
   # Paste as KUBE_CONFIG secret in GitHub
   ```

2. **SLACK_WEBHOOK** (optional)
   ```
   https://hooks.slack.com/services/T00000000/B00000000/XXXX
   ```

---

## 🛠️ Common Commands

```bash
make help              # Show all commands
make dev              # Start development
make test             # Run tests
make lint             # Run linter
make staging          # Start staging
make build            # Build Docker image
make push             # Push to registry
make deploy-staging   # Deploy to K8s staging
make deploy-prod      # Deploy to K8s production
make clean            # Stop containers
make clean-all        # Full cleanup
```

---

## 📊 Environment Comparison

| Aspect | Dev | Staging | Production |
|--------|-----|---------|------------|
| Build | From source | From source | Pre-built image |
| Logging | DEBUG | DEBUG | INFO |
| Reload | Hot reload | No | No |
| Database | SQLite/in-memory | PostgreSQL | PostgreSQL |
| Cache | None | Redis | Redis |
| Replicas | 1 | 1 | 3+ (HPA) |
| Monitoring | Prometheus | Prometheus | Prometheus + Jaeger |

---

## ✅ Verification Checklist

- [ ] GitHub secrets added (KUBE_CONFIG, SLACK_WEBHOOK)
- [ ] Docker registry credentials working
- [ ] Kubernetes cluster accessible
- [ ] Environment files created (.env.staging, .env.prod)
- [ ] Local test passed (`make test`)
- [ ] Staging deployment tested (`make staging`)
- [ ] Git tag created and pushed

---

## 📚 Documentation

- **DEPLOYMENT_GUIDE.md** - Full deployment instructions
- **Makefile** - Command reference
- **k8s/deployment.yaml** - Kubernetes manifest details

---

## 🔗 Next Steps

1. Add GitHub secrets: https://github.com/${GITHUB_ORG}/your-repo/settings/secrets
2. Set placeholders in deployment files (`${REGISTRY_ORG}`, `${IMAGE_NAME}`, `${VH2_DOMAIN}`, `${GITHUB_ORG}`, `${ALLOWED_ORIGIN}`)
3. Test locally with `make staging`
4. Deploy to staging: `make deploy-staging`
5. Create git tag and push to trigger production pipeline

---

## 🆘 Troubleshooting

```bash
# View GitHub Actions logs
# https://github.com/${GITHUB_ORG}/your-repo/actions

# View Kubernetes deployment status
kubectl describe deployment control-plane-proxy -n control-plane

# View pod logs
kubectl logs -n control-plane -l app=control-plane-proxy -f

# Check resource usage
kubectl top nodes
kubectl top pods -n control-plane

# Rollback deployment
kubectl rollout undo deployment/control-plane-proxy -n control-plane
```

---

**Ready to deploy!** 🎉

Let me know if you need any adjustments.
