# Kubernetes Deployment for Railway Intelligence Engine

This directory contains Kubernetes manifests for deploying the Railway Intelligence Engine to a Kubernetes cluster.

## Prerequisites

- Kubernetes cluster (minikube, k3s, EKS, GKE, etc.)
- kubectl configured
- Docker images built and available in registry
- NGINX Ingress Controller installed

## Deployment Order

1. **Infrastructure Services:**
   ```bash
   kubectl apply -f configmap.yaml
   kubectl apply -f postgres.yaml
   kubectl apply -f redis.yaml
   kubectl apply -f kafka.yaml
   ```

2. **Application Services:**
   ```bash
   kubectl apply -f scraper.yaml
   kubectl apply -f etl.yaml
   kubectl apply -f route-service.yaml
   kubectl apply -f rl-service.yaml  # Requires TensorFlow image
   ```

3. **Networking & Scaling:**
   ```bash
   kubectl apply -f ingress.yaml
   kubectl apply -f hpa.yaml
   ```

## Services

- **scraper**: Web scraping microservice (port 8001)
- **etl**: Data processing service
- **route-service**: Route optimization with RAPTOR algorithm (port 8002)
- **rl-service**: Reinforcement learning recommendations (port 8003)

## Scaling

- Route service has HPA configured for CPU/memory scaling
- Other services can be scaled manually: `kubectl scale deployment route-service --replicas=5`

## Monitoring

The services expose metrics endpoints for Prometheus:
- `/metrics` on each service

## Troubleshooting

1. Check pod status: `kubectl get pods`
2. View logs: `kubectl logs <pod-name>`
3. Check services: `kubectl get services`
4. Test ingress: `curl http://railway.local/api/routes/health`

## Production Considerations

- Use persistent volumes for PostgreSQL data
- Configure proper resource limits
- Set up proper RBAC
- Use secrets for sensitive data
- Configure TLS for ingress
- Set up proper monitoring and alerting