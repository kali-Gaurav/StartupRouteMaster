# Operational Runbook: Railway Emergency Intelligence Platform

## System Overview
The platform provides real-time train movement intelligence and emergency SOS response. 
Core components:
- **WebSocket Manager**: Distributed across nodes via Redis Pub/Sub.
- **Alert Manager**: Enriches SOS alerts with interpolated positions.
- **Position Broadcaster**: Background ticker (3s) for movement updates.

## Incident Response: SOS Surge Handling
**Scenario**: Sudden burst of >100 SOS alerts per minute.
1. **Monitor**: Check `sos_broadcast_latency_seconds`. If P95 > 500ms, the system is bottlenecked.
2. **Action**: Scale the `backend-api` deployment. 
3. **Action**: Verify Redis total memory (`info memory`). SOS enrichment utilizes Redis for state catch-up.

## Recovery: Redis Failure
**Scenario**: Prometheus reports `redis_health_checks_total{status="fail"}`.
1. **Behavior**: WebSockets will fall back to **Local Mode**. Alerts on Node A will NOT be visible on Node B.
2. **Verification**: Check if nodes can still ping the Redis cluster.
3. **Recovery**: 
   - Restart Redis cluster.
   - The `ConnectionManager` will automatically attempt to re-initialize on the next connection.
   - Force a restart of `position-broadcaster` instances to re-establish the primary ticker.

## Deployment Checklist (Production)
- [ ] **TLS**: Ensure `wss://` is used for all WebSocket connections.
- [ ] **Rate Limiting**: Verify `/api/sos` has tighter rate limits than general search.
- [ ] **Observability**: Ensure Grafana is scraping `/metrics` every 15s.
- [ ] **Security**: Verify `SECRET_KEY` is rotated and managed via AWS Secrets Manager / HashiCorp Vault.

## Resource Scaling
- **1,000 Users**: 2x Pods (2 vCPU, 4GB RAM each).
- **10,000 Users**: 5x Pods + Redis Cluster (min 3 nodes).
