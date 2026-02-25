# Parameterized Deployment Setup

This repository uses parameterized placeholders so deployment files stay reusable and environment-agnostic.

## Canonical Placeholders

- `${REGISTRY_ORG}`: Container registry org path (example: `ghcr.io/myorg`)
- `${IMAGE_NAME}`: Image name (example: `control-plane`)
- `${VH2_DOMAIN}`: Public domain (example: `vh2.example.com`)
- `${GITHUB_ORG}`: GitHub organization (example: `myorg`)
- `${ALLOWED_ORIGIN}`: Allowed CORS origin (example: `https://vh2.example.com`)

## Apply Real Values

Use the setup script to replace placeholders with your production values:

```bash
./setup-production.sh \
  --registry ghcr.io/myorg \
  --image control-plane \
  --domain vh2.example.com \
  --github-org myorg \
  --allowed-origin https://vh2.example.com
```

## Replacement Points

- `${REGISTRY_ORG}` and `${IMAGE_NAME}`:
  - `docker-compose.prod.yaml`
  - `k8s/deployment.yaml`
  - `k8s/extras.yaml`
  - `k8s/bytesampler-deployment.yaml`
  - `.github/workflows/deploy.yml`
  - `.github/workflows/docker-build-push.yml`
- `${VH2_DOMAIN}`:
  - `k8s/bytesampler-ingress.yaml`
- `${ALLOWED_ORIGIN}`:
  - `k8s/deployment.yaml`
  - `k8s/bytesampler-deployment.yaml`
- `${GITHUB_ORG}`:
  - `.github/workflows/deploy.yml`
  - `.github/workflows/docker-build-push.yml`
