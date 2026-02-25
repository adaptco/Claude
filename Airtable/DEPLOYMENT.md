# Production Deployment

This document outlines the steps to configure and deploy the application for a production environment. The process uses a script to substitute placeholder values in the Kubernetes manifests and GitHub Actions workflows with your environment-specific configuration.

## Configuration Parameters

The deployment script requires the following parameters:

-   `--registry`: The container registry organization where the application image is stored (e.g., `ghcr.io/myorg`).
-   `--image`: The name of the container image (e.g., `vh2-backend`).
-   `--domain`: The domain name where the application will be hosted (e.g., `vh2.example.com`).
-   `--github-org`: The GitHub organization or username that owns the repository (e.g., `myorg`).
-   `--allowed-origin`: The allowed origin for CORS, typically the application's domain (e.g., `https://vh2.example.com`).

## Setup Script

The `setup-production.sh` script automates the process of updating the configuration files.

```bash
#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 --registry REGISTRY_ORG --image IMAGE_NAME --domain VH2_DOMAIN --github-org GITHUB_ORG --allowed-origin ALLOWED_ORIGIN"
  exit 1
}

REGISTRY_ORG=""
IMAGE_NAME=""
VH2_DOMAIN=""
GITHUB_ORG=""
ALLOWED_ORIGIN=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --registry) REGISTRY_ORG="$2"; shift 2 ;;
    --image) IMAGE_NAME="$2"; shift 2 ;;
    --domain) VH2_DOMAIN="$2"; shift 2 ;;
    --github-org) GITHUB_ORG="$2"; shift 2 ;;
    --allowed-origin) ALLOWED_ORIGIN="$2"; shift 2 ;;
    *) usage ;;
  esac
done

[[ -z "$REGISTRY_ORG" || -z "$IMAGE_NAME" || -z "$VH2_DOMAIN" || -z "$GITHUB_ORG" || -z "$ALLOWED_ORIGIN" ]] && usage

# Patch Kubernetes manifests
find k8s -type f -name '*.yaml' -print0 | xargs -0 sed -i 
  -e "s|\${REGISTRY_ORG}|${REGISTRY_ORG}|g" 
  -e "s|\${IMAGE_NAME}|${IMAGE_NAME}|g" 
  -e "s|\${VH2_DOMAIN}|${VH2_DOMAIN}|g" 
  -e "s|\${ALLOWED_ORIGIN}|${ALLOWED_ORIGIN}|g"

# Patch GitHub Actions
find .github/workflows -type f -name '*.yml' -print0 | xargs -0 sed -i 
  -e "s|\${GITHUB_ORG}|${GITHUB_ORG}|g" 
  -e "s|\${REGISTRY_ORG}|${REGISTRY_ORG}|g" 
  -e "s|\${IMAGE_NAME}|${IMAGE_NAME}|g"

echo "Patched manifests and workflows with provided values."
```

### Usage

To run the script, provide the required parameters as command-line arguments.

**Example:**

```bash
./setup-production.sh 
  --registry ghcr.io/myorg 
  --image vh2-backend 
  --domain vh2.example.com 
  --github-org myorg 
  --allowed-origin https://vh2.example.com
```

This will replace the placeholders in the following files:

-   `k8s/deployment.yaml`
-   `k8s/ingress.yaml`
-   `k8s/service.yaml`
-   `.github/workflows/docker.yml`
-   `.github/workflows/mcp-tests.yml`
