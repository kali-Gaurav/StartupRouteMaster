"""
Monitoring Agent
===============
Watches for errors, slow queries, memory spikes.
"""
import logging
import psutil
import asyncio
from typing import Dict, Any, Optional
from services.agents.base_agent import BaseAgent

logger = logging.getLogger("agent.monitoring")

class MonitoringAgent(BaseAgent):
    """Monitors system health and performance"""
    
    def __init__(self):
        super().__init__()
        self.name = "MonitoringAgent"
        self.description = "Watches for errors, slow queries, and memory spikes"
        self.category = "monitoring"
        self.metrics_history = []
    
    async def on_start(self):
        """Initialize monitoring agent"""
        logger.info("📊 MonitoringAgent starting...")
        # Start background monitoring
        asyncio.create_task(self.background_monitoring())
        return True
    
    async def background_monitoring(self):
        """Background monitoring task"""
        iteration = 0
        while True:
            try:
                metrics = await self.collect_metrics()
                self.metrics_history.append(metrics)
                
                # Keep only last 100 metrics
                if len(self.metrics_history) > 100:
                    self.metrics_history = self.metrics_history[-100:]
                
                # 1. System Health Check
                await self.check_alerts(metrics)

                # 2. Operational Disruption Pulse (Every 15 iterations/mins)
                if iteration % 15 == 0:
                    await self.monitor_active_disruptions()
                
                iteration += 1
                
            except Exception as e:
                logger.error(f"❌ Monitoring error: {e}")
            
            await asyncio.sleep(60)  # Check every minute

    async def monitor_active_disruptions(self):
        """
        [Task 103.2] Operational Intelligence Sweep.
        Checks all near-term confirmed bookings for predicted disruptions.
        """
        from database.session import SessionLocal
        from database.models import Booking
        from services.booking_verification_service import booking_verification_service
        from datetime import datetime, timedelta
        
        logger.info("📡 [MONITOR] Starting Active Disruption Sweep...")
        db = SessionLocal()
        try:
            # Check bookings for the next 24 hours
            tomorrow = datetime.utcnow() + timedelta(days=1)
            active_bookings = db.query(Booking).filter(
                Booking.status == "CONFIRMED",
                Booking.travel_date >= datetime.utcnow().date(),
                Booking.travel_date <= tomorrow.date()
            ).all()

            for b in active_bookings:
                details = b.booking_details or {}
                # Manually invoke verification to trigger ML delay prediction
                check = await booking_verification_service.verify_booking_details(
                    train_number=details.get("train_number"),
                    travel_date=str(b.travel_date)
                )

                if "PREDICTIVE ALERT" in str(check.get("issues", [])) or "significantly delayed" in str(check.get("issues", [])):
                    logger.critical(f"🚨 DISRUPTION DETECTED: Booking {b.id} | Train {details.get('train_number')}")
                    # In a real sync, we'd trigger the NotificationService and ShadowEngine here.
                    # [Task 45.11] trigger_recovery_workflow(b.id, check)
            
        finally:
            db.close()
    
    async def collect_metrics(self) -> Dict[str, Any]:
        """Collect system metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            
            # Disk usage
            disk = psutil.disk_usage('/')
            
            # Process info
            process = psutil.Process()
            
            return {
                "timestamp": "2026-04-20T19:30:00Z",
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_used_mb": memory.used / (1024 * 1024),
                "memory_total_mb": memory.total / (1024 * 1024),
                "disk_percent": disk.percent,
                "disk_free_gb": disk.free / (1024 * 1024 * 1024),
                "process_memory_mb": process.memory_info().rss / (1024 * 1024),
                "process_threads": process.num_threads(),
            }
        except Exception as e:
            logger.error(f"❌ Metrics collection failed: {e}")
            return {"error": str(e)}
    
    async def check_alerts(self, metrics: Dict[str, Any]):
        """Check for alert conditions"""
        alerts = []
        
        # CPU alert
        if metrics.get("cpu_percent", 0) > 80:
            alerts.append({
                "type": "high_cpu",
                "value": metrics["cpu_percent"],
                "threshold": 80
            })
        
        # Memory alert
        if metrics.get("memory_percent", 0) > 85:
            alerts.append({
                "type": "high_memory",
                "value": metrics["memory_percent"],
                "threshold": 85
            })
        
        # Disk alert
        if metrics.get("disk_percent", 0) > 90:
            alerts.append({
                "type": "low_disk",
                "value": metrics["disk_percent"],
                "threshold": 90
            })
        
        if alerts:
            logger.warning(f"⚠️ System alerts: {alerts}")
            # Here you could send notifications, log to database, etc.
    
    async def get_system_health(self, **kwargs) -> Dict[str, Any]:
        """Get current system health status"""
        metrics = await self.collect_metrics()
        
        # Determine overall health
        health_status = "healthy"
        if metrics.get("cpu_percent", 0) > 80:
            health_status = "degraded"
        if metrics.get("memory_percent", 0) > 90:
            health_status = "critical"
        
        return {
            "operation": "health_check",
            "status": health_status,
            "metrics": metrics,
            "alerts": len(self.metrics_history) > 0 and any(
                m.get("cpu_percent", 0) > 80 or 
                m.get("memory_percent", 0) > 85 
                for m in self.metrics_history[-5:]  # Last 5 minutes
            )
        }
    
    async def get_performance_report(self, **kwargs) -> Dict[str, Any]:
        """Get performance report"""
        if not self.metrics_history:
            metrics = await self.collect_metrics()
            self.metrics_history.append(metrics)
        
        recent_metrics = self.metrics_history[-10:]  # Last 10 readings
        
        # Calculate averages
        avg_cpu = sum(m.get("cpu_percent", 0) for m in recent_metrics) / len(recent_metrics)
        avg_memory = sum(m.get("memory_percent", 0) for m in recent_metrics) / len(recent_metrics)
        
        return {
            "operation": "performance_report",
            "status": "completed",
            "avg_cpu_percent": avg_cpu,
            "avg_memory_percent": avg_memory,
            "sample_count": len(recent_metrics),
            "recommendations": [
                "Consider scaling if CPU > 70% consistently",
                "Monitor memory usage for leaks",
                "Review database query performance"
            ]
        }
    
    async def execute(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute monitoring task"""
        context = context or {}
        task = str(context.get("task", "")).lower()
        
        if "health" in task:
            return await self.get_system_health(**context)
        elif "performance" in task or "report" in task:
            return await self.get_performance_report(**context)
        elif "metrics" in task:
            metrics = await self.collect_metrics()
            return {
                "operation": "get_metrics",
                "status": "completed",
                "metrics": metrics
            }
        else:
            return {
                "operation": "unknown",
                "status": "failed",
                "error": f"Unknown monitoring task: {task}"
            }
