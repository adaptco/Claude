# Deployment Packaging Bundle

This repository now includes a placeholder-driven deploy bundle for the Python MCP server:

- `Dockerfile`
- `k8s/deployment.yaml`
- `k8s/service.yaml`
- `k8s/ingress.yaml` (optional to apply)
- `deploy.sh`

## Required Environment Variables

`deploy.sh` requires exactly these four variables:

```bash
DOCKER_REGISTRY_URL=...
PRODUCTION_DOMAIN=...
GITHUB_ORG_FOR_ARGOCD=...
ALLOWED_CORS_ORIGIN=...
```

## One-Command Deploy

```bash
DOCKER_REGISTRY_URL=... \
PRODUCTION_DOMAIN=... \
GITHUB_ORG_FOR_ARGOCD=... \
ALLOWED_CORS_ORIGIN=... \
./deploy.sh
```

## Optional Variables

- `IMAGE_NAME` (default: `a2a-digital-twin`)
- `IMAGE_TAG` (default: git short SHA, fallback timestamp)
- `K8S_NAMESPACE` (default: `a2a-digital-twin`)
- `ENABLE_INGRESS` (default: `true`)

## Notes

- Rendered manifests are written to `k8s/.rendered/`.
- `GITHUB_ORG_FOR_ARGOCD` is wired into the deployment annotation as an ArgoCD owner marker.
- Runtime secrets can be provided via an optional Kubernetes secret named `a2a-digital-twin-secrets`.
