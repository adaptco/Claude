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
