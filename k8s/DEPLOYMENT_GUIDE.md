# Kubernetes Deployment Guide for Bytesampler Adapter

## Overview

The Kubernetes manifests are organized into three files:

1. **bytesampler-deployment.yaml** - Core deployment resources (Deployment, Service, ConfigMap, Secret, HPA, PDB)
2. **bytesampler-rbac.yaml** - RBAC and NetworkPolicy
3. **bytesampler-ingress.yaml** - Ingress and monitoring (optional)

## Prerequisites

- Kubernetes cluster v1.20+ (1.24+ recommended)
- kubectl configured with access to your cluster
- Docker image pushed to a registry (e.g., `${REGISTRY_ORG}/${IMAGE_NAME}:latest`)
- Optional: Ingress controller (nginx-ingress), cert-manager, Prometheus Operator

## Step 1: Build and Push Docker Image

```bash
# Build the image
docker build -t ${REGISTRY_ORG}/${IMAGE_NAME}:latest .

# Push to registry
docker push ${REGISTRY_ORG}/${IMAGE_NAME}:latest
```

## Step 2: Update Configuration

Edit `bytesampler-deployment.yaml` and update:

1. **Image Registry**: Set `${REGISTRY_ORG}` and `${IMAGE_NAME}` to your actual image path
2. **Secrets**: Update `bytesampler-secrets` with actual database URL, API keys, etc.:

```yaml
stringData:
  DATABASE_URL: "postgresql://user:password@postgres-host:5432/dbname"
  API_KEY: "your-actual-api-key"
```

For production, use external secrets management:
- AWS Secrets Manager (with External Secrets Operator)
- Azure Key Vault
- Sealed Secrets
- HashiCorp Vault

## Step 3: Deploy Core Resources

Deploy the main application:

```bash
# Deploy namespace, ConfigMap, Secret, ServiceAccount, Deployment, Service, HPA, PDB
kubectl apply -f k8s/bytesampler-deployment.yaml

# Verify deployment
kubectl get pods -n bytesampler
kubectl get svc -n bytesampler
kubectl get deployment -n bytesampler
```

Watch rollout status:

```bash
kubectl rollout status deployment/bytesampler-adapter -n bytesampler
```

## Step 4: Apply RBAC and Network Policies

```bash
# Deploy RBAC and NetworkPolicy
kubectl apply -f k8s/bytesampler-rbac.yaml

# Verify
kubectl get roles,rolebindings,networkpolicies -n bytesampler
```

## Step 5: Setup Ingress (Optional)

First, ensure you have an ingress controller:

```bash
# Check if nginx-ingress is installed
kubectl get pods -n ingress-nginx
```

If not installed:

```bash
# Install ingress-nginx
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm install ingress-nginx ingress-nginx/ingress-nginx -n ingress-nginx --create-namespace
```

Then deploy Ingress:

```bash
# Set ${VH2_DOMAIN} in bytesampler-ingress.yaml
kubectl apply -f k8s/bytesampler-ingress.yaml

# Verify
kubectl get ingress -n bytesampler
```

## Step 6: Verify Deployment

Check pods are running:

```bash
kubectl get pods -n bytesampler -o wide
```

Check logs:

```bash
# Real-time logs from all replicas
kubectl logs -n bytesampler -l app=bytesampler-adapter -f --all-containers=true

# Logs from specific pod
kubectl logs -n bytesampler bytesampler-adapter-<pod-id>
```

Check service endpoints:

```bash
kubectl get endpoints -n bytesampler
```

Test connectivity (from inside cluster):

```bash
# Port forward for local testing
kubectl port-forward -n bytesampler svc/bytesampler-adapter 8000:80

# In another terminal
curl http://localhost:8000
```

## Scaling and Autoscaling

### Manual Scaling

```bash
# Scale to 5 replicas
kubectl scale deployment bytesampler-adapter --replicas=5 -n bytesampler
```

### Autoscaling (HPA)

The HPA is configured to:
- Minimum: 3 replicas
- Maximum: 10 replicas
- CPU target: 70% utilization
- Memory target: 80% utilization

Monitor autoscaling:

```bash
kubectl get hpa -n bytesampler -w
```

## Updating the Application

### Rolling Update (Default)

```bash
# Update image
kubectl set image deployment/bytesampler-adapter \
  bytesampler=${REGISTRY_ORG}/${IMAGE_NAME}:v2.0 \
  -n bytesampler

# Watch rollout
kubectl rollout status deployment/bytesampler-adapter -n bytesampler
```

### Rollback

```bash
# Rollback to previous revision
kubectl rollout undo deployment/bytesampler-adapter -n bytesampler

# Rollback to specific revision
kubectl rollout undo deployment/bytesampler-adapter --to-revision=2 -n bytesampler
```

## Resource Management

### Check Resource Usage

```bash
# View actual resource consumption
kubectl top pod -n bytesampler

# View node resources
kubectl top nodes
```

### Adjust Resource Requests/Limits

Edit `bytesampler-deployment.yaml` and update the `resources` section:

```yaml
resources:
  requests:
    cpu: 200m        # Requested CPU
    memory: 256Mi    # Requested memory
  limits:
    cpu: 500m        # Maximum CPU
    memory: 512Mi    # Maximum memory
```

Then reapply:

```bash
kubectl apply -f k8s/bytesampler-deployment.yaml
```

## Troubleshooting

### Pods not starting

```bash
# Check pod status and events
kubectl describe pod <pod-name> -n bytesampler

# Check logs
kubectl logs <pod-name> -n bytesampler --previous  # If crashed
```

### CrashLoopBackOff

```bash
# Check events
kubectl get events -n bytesampler --sort-by='.lastTimestamp'

# Check logs
kubectl logs <pod-name> -n bytesampler -p
```

### ImagePullBackOff

```bash
# Verify image exists in registry
docker inspect ${REGISTRY_ORG}/${IMAGE_NAME}:latest

# Check image pull policy and credentials
kubectl describe pod <pod-name> -n bytesampler
```

### Service endpoints not ready

```bash
# Check endpoint configuration
kubectl get endpoints -n bytesampler

# Check readiness probe
kubectl logs <pod-name> -n bytesampler
```

## Production Best Practices

1. **Use specific image tags** (not `latest`):
   ```yaml
   image: ${REGISTRY_ORG}/${IMAGE_NAME}:v1.0.0
   ```

2. **Manage secrets securely**:
   - Never commit secrets to git
   - Use external secrets operator or sealed-secrets
   - Rotate credentials regularly

3. **Monitor and logging**:
   - Deploy Prometheus for metrics
   - Deploy ELK/Loki for logs
   - Set up alerting rules

4. **Backup and disaster recovery**:
   - Enable etcd backup on your cluster
   - Use GitOps (ArgoCD, Flux) for configuration management

5. **Network policies**:
   - Start with restrictive policies (as provided)
   - Gradually expand based on requirements
   - Monitor denied connections

6. **Resource limits**:
   - Set appropriate requests and limits
   - Monitor actual usage and adjust
   - Use VPA (Vertical Pod Autoscaler) for recommendations

## Undeployment

Remove all resources:

```bash
kubectl delete -f k8s/bytesampler-ingress.yaml
kubectl delete -f k8s/bytesampler-rbac.yaml
kubectl delete -f k8s/bytesampler-deployment.yaml
```

Or delete the entire namespace:

```bash
kubectl delete namespace bytesampler
```

## Resources

- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [kubectl Reference](https://kubernetes.io/docs/reference/kubectl/)
- [Deployment Strategy](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#strategy)
- [HPA Documentation](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
- [NetworkPolicy Guide](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
