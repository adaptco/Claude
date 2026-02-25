#!/bin/bash

# Quick setup script for deployment pipeline

set -e

echo "=== Control Plane Deployment Pipeline Setup ==="
echo ""

# Check prerequisites
echo "Checking prerequisites..."
command -v git >/dev/null 2>&1 || { echo "❌ git not found"; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "❌ docker not found"; exit 1; }
echo "✅ Prerequisites OK"
echo ""

# Copy environment files
echo "Setting up environment files..."
if [ ! -f .env.staging ]; then
    cp .env.staging.example .env.staging
    echo "✅ Created .env.staging (edit with your values)"
else
    echo "ℹ️  .env.staging already exists"
fi

if [ ! -f .env.prod ]; then
    cp .env.prod.example .env.prod
    echo "✅ Created .env.prod (edit with your values)"
else
    echo "ℹ️  .env.prod already exists"
fi
echo ""

# Create directories
echo "Creating directory structure..."
mkdir -p k8s monitoring logs
echo "✅ Directories created"
echo ""

# Build options
echo "What would you like to do?"
echo ""
echo "1) Start development environment"
echo "2) Start staging environment"
echo "3) Build Docker image locally"
echo "4) Deploy to Kubernetes"
echo "5) Show deployment status"
echo "6) Exit"
echo ""
read -p "Enter choice (1-6): " choice

case $choice in
    1)
        echo "Starting development..."
        docker compose -f compose.dev.yaml up -d
        echo "✅ Development running on http://localhost:8080"
        ;;
    2)
        echo "Starting staging..."
        docker compose -f docker-compose.staging.yaml up -d
        echo "✅ Staging running on http://localhost:8080"
        ;;
    3)
        echo "Building Docker image..."
        docker build -t control-plane:latest .
        echo "✅ Image built"
        ;;
    4)
        echo "Checking kubectl..."
        command -v kubectl >/dev/null 2>&1 || { echo "❌ kubectl not found"; exit 1; }
        echo "Deploying to Kubernetes..."
        kubectl apply -f k8s/rbac.yaml
        kubectl apply -f k8s/deployment.yaml
        kubectl apply -f k8s/extras.yaml
        echo "✅ Deployment applied"
        ;;
    5)
        echo "Deployment Status:"
        echo ""
        echo "Docker Compose (dev):"
        docker compose -f compose.dev.yaml ps 2>/dev/null || echo "Not running"
        echo ""
        echo "Docker Compose (staging):"
        docker compose -f docker-compose.staging.yaml ps 2>/dev/null || echo "Not running"
        echo ""
        if command -v kubectl >/dev/null 2>&1; then
            echo "Kubernetes:"
            kubectl get deployment -n control-plane 2>/dev/null || echo "Not deployed"
        fi
        ;;
    6)
        echo "Exiting..."
        exit 0
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Edit .env.staging and .env.prod with your configuration"
echo "2. Run 'make help' to see all available commands"
echo "3. Run 'make dev' to start development"
echo "4. Check DEPLOYMENT_GUIDE.md for detailed instructions"
echo ""
