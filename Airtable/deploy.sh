#!/usr/bin/env bash
set -euo pipefail

required_vars=(
  DOCKER_REGISTRY_URL
  PRODUCTION_DOMAIN
  GITHUB_ORG_FOR_ARGOCD
  ALLOWED_CORS_ORIGIN
)

for var_name in "${required_vars[@]}"; do
  if [[ -z "${!var_name:-}" ]]; then
    echo "Missing required env var: ${var_name}" >&2
    exit 1
  fi
done

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required but not found in PATH." >&2
  exit 1
fi

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl is required but not found in PATH." >&2
  exit 1
fi

IMAGE_NAME="${IMAGE_NAME:-a2a-digital-twin}"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)}"
K8S_NAMESPACE="${K8S_NAMESPACE:-a2a-digital-twin}"
ENABLE_INGRESS="${ENABLE_INGRESS:-true}"

registry="${DOCKER_REGISTRY_URL%/}"
IMAGE_REF="${registry}/${IMAGE_NAME}:${IMAGE_TAG}"

echo "[1/5] Building image: ${IMAGE_REF}"
docker build -f Dockerfile -t "${IMAGE_REF}" .

echo "[2/5] Pushing image: ${IMAGE_REF}"
docker push "${IMAGE_REF}"

escape_sed() {
  printf '%s' "$1" | sed -e 's/[\/&]/\\&/g'
}

render_file() {
  local src="$1"
  local dst="$2"

  sed \
    -e "s/__IMAGE__/$(escape_sed "${IMAGE_REF}")/g" \
    -e "s/__PRODUCTION_DOMAIN__/$(escape_sed "${PRODUCTION_DOMAIN}")/g" \
    -e "s/__GITHUB_ORG_FOR_ARGOCD__/$(escape_sed "${GITHUB_ORG_FOR_ARGOCD}")/g" \
    -e "s/__ALLOWED_CORS_ORIGIN__/$(escape_sed "${ALLOWED_CORS_ORIGIN}")/g" \
    "${src}" > "${dst}"
}

render_dir="k8s/.rendered"
mkdir -p "${render_dir}"

echo "[3/5] Rendering manifests into ${render_dir}"
render_file "k8s/deployment.yaml" "${render_dir}/deployment.yaml"
render_file "k8s/service.yaml" "${render_dir}/service.yaml"
render_file "k8s/ingress.yaml" "${render_dir}/ingress.yaml"

echo "[4/5] Applying manifests to namespace ${K8S_NAMESPACE}"
kubectl get namespace "${K8S_NAMESPACE}" >/dev/null 2>&1 || kubectl create namespace "${K8S_NAMESPACE}"
kubectl -n "${K8S_NAMESPACE}" apply -f "${render_dir}/deployment.yaml"
kubectl -n "${K8S_NAMESPACE}" apply -f "${render_dir}/service.yaml"

if [[ "${ENABLE_INGRESS}" == "true" ]]; then
  kubectl -n "${K8S_NAMESPACE}" apply -f "${render_dir}/ingress.yaml"
else
  echo "Ingress apply skipped (ENABLE_INGRESS=${ENABLE_INGRESS})."
fi

echo "[5/5] Deploy completed"
echo "Image: ${IMAGE_REF}"
echo "Namespace: ${K8S_NAMESPACE}"
echo "Domain: ${PRODUCTION_DOMAIN}"
echo "ArgoCD org marker: ${GITHUB_ORG_FOR_ARGOCD}"
