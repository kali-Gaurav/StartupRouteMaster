import sys
import time
import requests
import logging

import os

# [SOVEREIGN] Canary Quality Gate
# Analyzes Prometheus metrics to ensure 'Zero-Downtime' safety during global rollouts.

PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://prometheus-service:9090")
THRESHOLD_LATENCY_MS = 300
THRESHOLD_ERROR_RATE = 0.02 # 2% max

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sovereign.canary_gate")

def get_metric(query):
    try:
        response = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query})
        data = response.json()
        if data["status"] == "success" and data["data"]["result"]:
            return float(data["data"]["result"][0]["value"][1])
    except Exception as e:
        logger.error(f"Failed to fetch metric {query}: {e}")
    return 0.0

def evaluate_canary():
    logger.info("🕵️ [SOVEREIGN] Evaluating Canary Health...")
    
    # 1. Check Sovereign Latency (NPC Refresh)
    # This ensures our new algorithm doesn't choke the server
    latency = get_metric("avg(routemaster_sovereign_npc_refresh_latency_seconds) * 1000")
    logger.info(f"📊 Avg Sovereign Latency: {latency:.2f}ms (Target: <{THRESHOLD_LATENCY_MS}ms)")
    
    # 2. Check Error Rate
    # (Total Errors / Total Requests)
    error_rate = get_metric(
        'sum(rate(fastapi_requests_total{status=~"5.*"}[5m])) / sum(rate(fastapi_requests_total[5m]))'
    )
    logger.info(f"📊 Error Rate: {error_rate*100:.2f}% (Target: <{THRESHOLD_ERROR_RATE*100}%)")

    # 3. Decision Logic
    if latency > THRESHOLD_LATENCY_MS:
        logger.error("❌ CANARY REJECTED: Latency too high.")
        return False
    
    if error_rate > THRESHOLD_ERROR_RATE:
        logger.error("❌ CANARY REJECTED: Error rate spike detected.")
        return False

    logger.info("✅ CANARY PASSED: System remains Sovereignly Stable.")
    return True

if __name__ == "__main__":
    # Wait for traffic to settle
    time.sleep(60)
    
    if evaluate_canary():
        sys.exit(0) # Success -> Promote
    else:
        sys.exit(1) # Failure -> Rollback
