#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./setup-production.sh \
    --registry REGISTRY_ORG \
    --image IMAGE_NAME \
    --domain VH2_DOMAIN \
    --github-org GITHUB_ORG \
    --allowed-origin ALLOWED_ORIGIN

Example:
  ./setup-production.sh \
    --registry ghcr.io/myorg \
    --image control-plane \
    --domain vh2.example.com \
    --github-org myorg \
    --allowed-origin https://vh2.example.com
EOF
  exit 1
}

REGISTRY_ORG=""
IMAGE_NAME=""
VH2_DOMAIN=""
GITHUB_ORG=""
ALLOWED_ORIGIN=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --registry)
      REGISTRY_ORG="${2:-}"
      shift 2
      ;;
    --image)
      IMAGE_NAME="${2:-}"
      shift 2
      ;;
    --domain)
      VH2_DOMAIN="${2:-}"
      shift 2
      ;;
    --github-org)
      GITHUB_ORG="${2:-}"
      shift 2
      ;;
    --allowed-origin)
      ALLOWED_ORIGIN="${2:-}"
      shift 2
      ;;
    *)
      usage
      ;;
  esac
done

if [[ -z "$REGISTRY_ORG" || -z "$IMAGE_NAME" || -z "$VH2_DOMAIN" || -z "$GITHUB_ORG" || -z "$ALLOWED_ORIGIN" ]]; then
  usage
fi

patch_file() {
  local target="$1"
  sed -i.bak \
    -e "s|\${REGISTRY_ORG}|${REGISTRY_ORG}|g" \
    -e "s|\${IMAGE_NAME}|${IMAGE_NAME}|g" \
    -e "s|\${VH2_DOMAIN}|${VH2_DOMAIN}|g" \
    -e "s|\${GITHUB_ORG}|${GITHUB_ORG}|g" \
    -e "s|\${ALLOWED_ORIGIN}|${ALLOWED_ORIGIN}|g" \
    "$target"
  rm -f "${target}.bak"
}

while IFS= read -r -d '' file; do
  patch_file "$file"
done < <(find k8s -type f \( -name '*.yaml' -o -name '*.yml' \) -print0)

while IFS= read -r -d '' file; do
  patch_file "$file"
done < <(find .github/workflows -type f -name '*.yml' -print0)

if [[ -f "docker-compose.prod.yaml" ]]; then
  patch_file "docker-compose.prod.yaml"
fi

echo "Patched k8s manifests, workflows, and docker-compose.prod.yaml with provided values."
