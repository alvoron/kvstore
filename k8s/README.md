# Kubernetes Manifests for kvstore

This directory contains Kubernetes manifest files for deploying kvstore in a production environment.

## Files

- **namespace.yaml** - Creates the `kvstore` namespace
- **configmap.yaml** - Configuration for master ordinal and replication settings
- **service-headless.yaml** - Headless service for pod-to-pod communication
- **service-master.yaml** - LoadBalancer service for client access to master
- **statefulset.yaml** - Main StatefulSet with 3 replicas
- **pdb.yaml** - PodDisruptionBudget to ensure minimum availability
- **networkpolicy.yaml** - Network policies for security
- **cronjob-backup.yaml** - Daily backup CronJob

## Quick Deploy

```bash
# Deploy all manifests
kubectl apply -f k8s/

# Or deploy in order
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/service-headless.yaml
kubectl apply -f k8s/service-master.yaml
kubectl apply -f k8s/statefulset.yaml
kubectl apply -f k8s/pdb.yaml
kubectl apply -f k8s/networkpolicy.yaml

# Optional: Deploy backup CronJob
kubectl apply -f k8s/cronjob-backup.yaml
```

## Verify Deployment

```bash
# Check pods
kubectl get pods -n kvstore

# Check services
kubectl get svc -n kvstore

# Check persistent volumes
kubectl get pvc -n kvstore
```

## Configuration

Before deploying, review and customize:

1. **statefulset.yaml**:
   - Update `storageClassName` to match your cluster
   - Adjust resource requests/limits
   - Change `hostPath` volume to use your kvstore source path or use a Docker image

2. **configmap.yaml**:
   - Set `MASTER_ORDINAL` to choose which pod is master (0, 1, or 2)
   - Configure `REPLICATION_MODE` (async or sync)

3. **service-master.yaml**:
   - Change `type` to `ClusterIP` for internal-only access

## See Also

- [docs/KUBERNETES.md](../docs/KUBERNETES.md) - Complete deployment guide
- [docs/REPLICATION.md](../docs/REPLICATION.md) - Replication architecture
