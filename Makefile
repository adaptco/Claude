.PHONY: help test lint build push deploy-staging deploy-prod clean

REGISTRY := ghcr.io
ORG := your-org
IMAGE_NAME := control-plane
VERSION := $(shell git describe --tags --always --dirty)
IMAGE := $(REGISTRY)/$(ORG)/$(IMAGE_NAME):$(VERSION)

help:
	@echo "Control Plane Deployment Pipeline"
	@echo ""
	@echo "Development:"
	@echo "  make dev              - Start development environment"
	@echo "  make test             - Run tests"
	@echo "  make lint             - Run linter"
	@echo "  make dev-logs         - View dev logs"
	@echo ""
	@echo "Staging:"
	@echo "  make staging          - Start staging environment"
	@echo "  make staging-logs     - View staging logs"
	@echo ""
	@echo "Production:"
	@echo "  make build            - Build Docker image"
	@echo "  make push             - Push to registry"
	@echo "  make deploy-prod      - Deploy to Kubernetes production"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean            - Stop all containers"
	@echo "  make clean-all        - Full cleanup (including volumes)"

# Development
dev:
	docker compose -f compose.dev.yaml up -d
	@echo "Development environment running on http://localhost:8080"

dev-logs:
	docker compose -f compose.dev.yaml logs control-plane-proxy -f

test:
	docker compose -f compose.dev.yaml exec control-plane-proxy \
		pytest tests/test_harness.py -v --tb=short

lint:
	docker compose -f compose.dev.yaml exec control-plane-proxy \
		pylint bytesampler_adapter.py --rcfile=.pylintrc

# Staging
staging:
	docker compose -f docker-compose.staging.yaml up -d
	@echo "Staging environment running on http://localhost:8080"

staging-logs:
	docker compose -f docker-compose.staging.yaml logs control-plane-proxy -f

staging-db-init:
	docker compose -f docker-compose.staging.yaml exec postgres \
		psql -U vvl -d vvl_staging -f /app/init-schema.sql

# Production (Docker Compose)
prod-up:
	@echo "Starting production environment..."
	docker compose -f docker-compose.prod.yaml up -d
	@echo "Waiting for health check..."
	@sleep 10
	docker compose -f docker-compose.prod.yaml ps

prod-down:
	docker compose -f docker-compose.prod.yaml down

prod-logs:
	docker compose -f docker-compose.prod.yaml logs control-plane-proxy -f

# Docker Build & Push
build:
	docker buildx build \
		--platform linux/amd64,linux/arm64 \
		-t $(IMAGE) \
		-t $(REGISTRY)/$(ORG)/$(IMAGE_NAME):latest \
		.

build-local:
	docker build -t $(IMAGE) .

push: build-local
	docker push $(IMAGE)
	docker push $(REGISTRY)/$(ORG)/$(IMAGE_NAME):latest

scan:
	@command -v trivy >/dev/null || { echo "Installing Trivy..."; go install github.com/aquasecurity/trivy@latest; }
	trivy image $(IMAGE)

# Kubernetes
deploy-staging:
	kubectl apply -f k8s/rbac.yaml
	kubectl apply -f k8s/deployment.yaml
	kubectl apply -f k8s/extras.yaml
	kubectl -n control-plane rollout status deployment/control-plane-proxy

deploy-prod:
	@echo "Deploying to production..."
	kubectl apply -f k8s/rbac.yaml
	kubectl apply -f k8s/deployment.yaml
	kubectl apply -f k8s/extras.yaml
	kubectl -n control-plane set image deployment/control-plane-proxy \
		control-plane=$(IMAGE) --record
	kubectl -n control-plane rollout status deployment/control-plane-proxy --timeout=5m

k8s-logs:
	kubectl logs -n control-plane -l app=control-plane-proxy -f

k8s-status:
	kubectl get all -n control-plane
	kubectl describe deployment/control-plane-proxy -n control-plane

k8s-shell:
	kubectl exec -it -n control-plane \
		$(shell kubectl get pod -n control-plane -l app=control-plane-proxy -o jsonpath='{.items[0].metadata.name}') \
		-- /bin/sh

# Cleanup
stop:
	docker compose -f compose.dev.yaml down
	docker compose -f docker-compose.staging.yaml down
	docker compose -f docker-compose.prod.yaml down

clean: stop
	docker system prune -f

clean-all: stop
	docker system prune -af
	docker volume prune -f
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true

# Utilities
version:
	@echo "Current version: $(VERSION)"

shell-dev:
	docker compose -f compose.dev.yaml exec control-plane-proxy /bin/bash

shell-staging:
	docker compose -f docker-compose.staging.yaml exec control-plane-proxy /bin/bash

.DEFAULT_GOAL := help
