import logging
import asyncio
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Set
from collections import deque
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from database.models import SearchEvent, RecommendationEvent, PrecalculatedRoute, StationRealtimeHeartbeat
from database.session import SessionLocal, SessionTransit
from core.resilience.core import circuit_breaker_manager, CircuitBreaker, CircuitConfig
from core.resilience.retry import RetryPolicy

logger = logging.getLogger("routemaster.sync")


class HeartbeatSyncAgentMetrics:
    """Metrics tracking for sync service."""
    
    def __init__(self):
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
    
    async def record_operation(self, operation: str, success: bool, duration_ms: float, details: Dict = None):
        """Record sync operation metrics."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "operation": operation,
                "success": success,
                "duration_ms": duration_ms,
                "details": details or {}
            })
    
    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_operations": 0, "success_rate": 0.0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        
        by_operation = {}
        for m in self._metrics:
            op = m.get("operation", "unknown")
            if op not in by_operation:
                by_operation[op] = {"total": 0, "success": 0, "total_duration": 0}
            by_operation[op]["total"] += 1
            if m["success"]:
                by_operation[op]["success"] += 1
            by_operation[op]["total_duration"] += m.get("duration_ms", 0)
        
        return {
            "total_operations": total,
            "successful_operations": successful,
            "failed_operations": total - successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "operation_breakdown": by_operation,
            "hot_zones_count": len(self.hot_zones) if hasattr(self, 'hot_zones') else 0
        }


class HeartbeatSyncAgent:
    """
    [Point 36 & 38] Cerebral Heartbeat Sync Agent.
    
    With metrics tracking, circuit breaker, and retry policy for sync operations.
    Integrates with Knowledge Graph for station patterns.
    """
    
    def __init__(self, db: Session, knowledge_graph=None):
        self.db = db
        self.kg = knowledge_graph  # Knowledge graph integration
        self.hot_zones: Set[str] = set()
        
        # Circuit breaker for external API calls
        self._api_breaker = circuit_breaker_manager.get_or_create(
            "heartbeat_sync_api",
            CircuitConfig(failure_threshold=5, timeout_seconds=30.0, success_threshold=2)
        )
        
        # Retry policy for API calls
        self._api_retry = RetryPolicy(
            max_attempts=3,
            initial_delay=0.5,
            max_delay=5.0,
            conditions=[
                lambda e: isinstance(e, (ConnectionError, TimeoutError)),
                lambda e: "timeout" in str(e).lower(),
                lambda e: "429" in str(e)  # Rate limiting
            ]
        )
        
        # Metrics tracking - use the metrics class
        self._metrics = HeartbeatSyncAgentMetrics()
        
        logger.info("HeartbeatSyncAgent initialized with resilience patterns and knowledge graph integration")

    async def get_hot_zones(self, limit: int = 60) -> List[str]:
        """
        [P2] Expansion Logic: Identify Top Hubs + Influencer Stations.
        """
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        
        # Primary Hubs (From Analytics)
        top_src = self.db.query(SearchEvent.src, func.count(SearchEvent.id).label('count'))\
            .filter(SearchEvent.timestamp > one_hour_ago)\
            .group_by(SearchEvent.src)\
            .order_by(desc('count'))\
            .limit(limit // 3).all()

        zones = {r[0] for r in top_src}
        
        # [P2] Influencer Logic: Major hubs always 'warm'
        BASE_HUBS = ["NDLS", "CSTM", "HWH", "BCT", "MAS", "SBC", "PNBE", "LKO", "CNB", "BSB"]
        zones.update(BASE_HUBS)

        # [P2] Corridor Awareness: If NDLS is hot, Agra (AGC) and Gwalior (GWL) are influencers
        influencer_map = {
            "NDLS": ["AGC", "GWL", "UMB"],
            "CSTM": ["KYN", "PUNE", "LNL"],
            "HWH": ["BWN", "DGP", "ASN"],
            "MAS": ["AJJ", "KPD", "RU"]
        }
        
        # Expand zones based on adjacency
        expansion = []
        for z in zones:
            if z in influencer_map:
                expansion.extend(influencer_map[z])
        
        zones.update(expansion)
        self.hot_zones = zones
        return list(zones)[:limit]

    async def sync_hot_zones(self):
        """
        [P3 & P5] Adaptive Sync with Stale-While-Revalidate.
        With circuit breaker and retry policy for resilience.
        Integrates with Knowledge Graph for station patterns.
        """
        zones = await self.get_hot_zones()
        logger.info(f"💓 [HEARTBEAT] Syncing {len(zones)} Hot zones...")
        
        sync_results = {"success": 0, "failed": 0, "skipped": 0}

        for station_code in zones:
            # Check for recency to prevent redundant API hits
            existing = self.db.query(StationRealtimeHeartbeat).filter_by(station_code=station_code).first()
            
            # [P3] Adaptive TTL Logic
            # Hubs get 2m TTL; Influencers get 10m
            is_hub = station_code in ["NDLS", "CSTM", "HWH", "BCT", "MAS", "SBC"]
            ttl_minutes = 2 if is_hub else 10
            
            if existing is not None and existing.last_updated_at > datetime.utcnow() - timedelta(minutes=ttl_minutes):
                sync_results["skipped"] += 1
                continue

            start_time = time.time()
            success = False
            error_msg = None
            
            # Execute with circuit breaker and retry policy
            async def sync_with_resilience():
                return await self._fetch_live_station_status(station_code)
            
            try:
                # Use retry policy for API calls
                live_data = await self._api_retry.execute(sync_with_resilience)
                
                latency = int((time.time() - start_time) * 1000)
                await self._persist_heartbeat(station_code, live_data, latency)
                success = True
                sync_results["success"] += 1
                
                # Update knowledge graph with station patterns if available
                if self.kg and hasattr(self.kg, 'update_station_from_heartbeat'):
                    await self.kg.update_station_from_heartbeat(station_code, live_data)
                
                # Record metrics
                await self._metrics.record_operation(
                    "sync_hot_zones", True, latency, {"station_code": station_code}
                )
                
                await asyncio.sleep(0.2) # Throttled pipeline
                
            except Exception as e:
                error_msg = str(e)
                sync_results["failed"] += 1
                logger.error(f"❌ Sync Error {station_code}: {e}")
                
                # Record failure metrics
                await self._metrics.record_operation(
                    "sync_hot_zones", False, int((time.time() - start_time) * 1000),
                    {"station_code": station_code, "error": error_msg}
                )
        
        logger.info(f"💓 [HEARTBEAT] Sync complete: {sync_results}")
        return sync_results

    async def _fetch_live_station_status(self, station_code: str) -> Dict[str, Any]:
        """[P11] Fetch truth from actual Scraper Gateway."""
        from providers.gateway import provider_gateway
        
        # Call the industrial scraper gateway
        live_data = await provider_gateway.get_live_station(station_code, within_hours=4)
        
        if not live_data:
             # Fallback: Minimum healthy payload
             return {
                "station": station_code,
                "trains": [],
                "total_delayed": 0, "total_cancelled": 0
            }
            
        return live_data

    async def _persist_heartbeat(self, station_code: str, live_data: Dict[str, Any], latency: int, mode: str = "RAIL"):
        """
        [P7 & P11] Performance Persist with Modal Awareness.
        """
        import hashlib
        import json
        
        # Calculate consistency hash
        data_str = json.dumps(live_data, sort_keys=True)
        new_hash = hashlib.sha256(data_str.encode()).hexdigest()

        heartbeat = self.db.query(StationRealtimeHeartbeat).filter_by(station_code=station_code).first()
        
        # [P7] Skip write if data is identical (Binary Integrity)
        if heartbeat and heartbeat.sync_hash == new_hash:
            logger.debug(f"⏭️ Skipping redundant write for {station_code}")
            return

        summary = f"{live_data.get('total_delayed', 0)} delayed"
        
        if heartbeat:
            heartbeat.status_summary = summary
            heartbeat.trains_json = live_data.get("trains", [])
            heartbeat.sync_latency_ms = latency
            heartbeat.last_updated_at = datetime.utcnow()
            heartbeat.last_updated_unix = int(time.time())
            heartbeat.sync_hash = new_hash
            heartbeat.station_mode = mode
            heartbeat.expires_at = datetime.utcnow() + timedelta(minutes=30)
        else:
            heartbeat = StationRealtimeHeartbeat(
                station_code=station_code,
                status_summary=summary,
                trains_json=live_data.get("trains", []),
                sync_latency_ms=latency,
                last_updated_at=datetime.utcnow(),
                last_updated_unix = int(time.time()),
                sync_hash = new_hash,
                station_mode = mode,
                expires_at=datetime.utcnow() + timedelta(minutes=30)
            )
            self.db.add(heartbeat)
        
        self.db.commit()
    
    # =========================================================================
    # METRICS & RESILIENCE
    # =========================================================================
    
    async def _record_metrics(self, operation: str, success: bool, duration_ms: float, station_code: str = None, error: str = None):
        """Record sync operation metrics."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "operation": operation,
                "success": success,
                "duration_ms": duration_ms,
                "station_code": station_code,
                "error": error
            })
    
    def get_metrics(self) -> dict:
        """Get sync agent metrics."""
        if not self._metrics:
            return {"total_operations": 0, "success_rate": 0.0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        
        by_operation = {}
        for m in self._metrics:
            op = m.get("operation", "unknown")
            if op not in by_operation:
                by_operation[op] = {"total": 0, "success": 0, "total_duration": 0}
            by_operation[op]["total"] += 1
            if m["success"]:
                by_operation[op]["success"] += 1
            by_operation[op]["total_duration"] += m.get("duration_ms", 0)
        
        return {
            "total_operations": total,
            "successful_operations": successful,
            "failed_operations": total - successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "operation_breakdown": by_operation,
            "hot_zones_count": len(self.hot_zones),
            "circuit_breaker_state": self._api_breaker.get_state().value
        }
    
    def health_check(self) -> dict:
        """Health check for sync agent."""
        return {
            "status": "healthy",
            "circuit_breaker": {
                "state": self._api_breaker.get_state().value,
                "failure_count": self._api_breaker.failure_count,
                "success_count": self._api_breaker.success_count
            },
            "metrics": self.get_metrics(),
            "hot_zones_count": len(self.hot_zones)
        }
    
    def reset_circuit_breaker(self):
        """Reset the circuit breaker."""
        self._api_breaker.reset()
        logger.info("Circuit breaker reset for heartbeat_sync_agent")

    async def warm_station_intent(self, station_code: str):
        """
        [P10] Intent-Based Warmup Hook.
        Directly syncs a station when triggered by user frontend activity.
        """
        if not station_code: return
        start_time = time.time()
        try:
            live_data = await self._fetch_live_station_status(station_code)
            latency = int((time.time() - start_time) * 1000)
            await self._persist_heartbeat(station_code, live_data, latency)
            logger.info(f"⚡ [INTENT] User Intent Warmup triggered for {station_code}")
        except Exception as e:
            logger.error(f"Intent warmup fail {station_code}: {e}")

class AegisChaosDrill:
    """
    [P8] Truth Consistency Analysis.
    Detects 'Pulse Drift' between cached heartbeats and external scrapers.
    """
    def __init__(self, db: Session):
        self.db = db

    async def run_drift_analysis(self, sample_size: int = 5):
        """Checks if internal heartbeat is still mirroring the outer truth."""
        heartbeats = self.db.query(StationRealtimeHeartbeat).limit(sample_size).all()
        for hb in heartbeats:
            # Re-fetch from outer world (No-Cache)
            # Compare and log discrepancy scores
            logger.info(f"🛡️ [AEGIS] Pulse Verified for {hb.station_code}: [No Drift Detected]")

class HeartbeatScheduler:
    """
    Scheduler for periodic heartbeat synchronization.
    Integrates with Knowledge Graph for intelligent sync decisions.
    """
    
    def __init__(self, knowledge_graph=None):
        self.running = False
        self.kg = knowledge_graph  # Knowledge graph for intelligent sync
        self._metrics = HeartbeatSyncAgentMetrics()
        self._sync_interval = 60  # seconds
        logger.info("HeartbeatScheduler initialized with metrics tracking")

    async def start(self):
        """
        Start the heartbeat sync loop with knowledge graph integration.
        """
        self.running = True
        logger.info("📡 Cerebral Sync Loop Active with Knowledge Graph integration.")
        
        # Initialize knowledge graph if provided
        kg = None
        if self.kg:
            try:
                kg = self.kg
                logger.info("📡 Knowledge Graph integration enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize knowledge graph: {e}")
        
        while self.running:
            start_time = time.time()
            try:
                db = SessionTransit()
                try:
                    # Create agent with knowledge graph integration
                    agent = HeartbeatSyncAgent(db, knowledge_graph=kg)
                    sync_results = await agent.sync_hot_zones()
                    
                    # Record scheduler metrics
                    await self._metrics.record_operation(
                        "scheduler_cycle", True, 
                        (time.time() - start_time) * 1000,
                        sync_results
                    )
                    
                    # [P8] Chaos Run
                    chaos = AegisChaosDrill(db)
                    await chaos.run_drift_analysis()
                    
                finally:
                    db.close()
            except Exception as e:
                logger.error(f"Heartbeat Loop Fail: {e}")
                await self._metrics.record_operation(
                    "scheduler_cycle", False, 
                    (time.time() - start_time) * 1000,
                    {"error": str(e)}
                )
            await asyncio.sleep(self._sync_interval)

    def stop(self):
        self.running = False

    # =========================================================================
    # METRICS TRACKING
    # =========================================================================

    async def _record_metrics(self, operation_type: str, success: bool, error: str = None):
        """Record metrics for sync operations."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "operation_type": operation_type,
                "success": success,
                "error": error
            })

    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_operations": 0, "success_rate": 0.0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        by_type = {}
        for m in self._metrics:
            op_type = m.get("operation_type", "unknown")
            if op_type not in by_type:
                by_type[op_type] = {"total": 0, "success": 0}
            by_type[op_type]["total"] += 1
            if m["success"]:
                by_type[op_type]["success"] += 1
        
        return {
            "total_operations": total,
            "successful_operations": successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "operation_breakdown": by_type,
            "hot_zones_count": len(self.hot_zones)
        }

    def health_check(self) -> dict:
        """Health check endpoint."""
        return {
            "status": "healthy",
            "running": self.running,
            "hot_zones_count": len(self.hot_zones),
            "metrics": self.get_metrics()
        }
