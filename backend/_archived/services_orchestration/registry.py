"""
Service Registry and Integration Manager

Provides unified initialization and dependency injection for all services.
Ensures proper integration between:
- User Service
- Knowledge Graph Service
- Demand Redistribution Service
- Sync Service
- Station Departure Service
"""

import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from database.session import SessionLocal, SessionTransit
from services.user_service import UserService
from services.knowledge_graph_service import TravelKnowledgeGraph
from services.demand_redistribution_service import DemandRedistributionService, get_redistribution_service
from services.sync_service import HeartbeatSyncAgent, HeartbeatScheduler
from services.station_departure_service import StationDepartureService

logger = logging.getLogger("service.registry")


class ServiceRegistry:
    """
    Central registry for all services with dependency injection.
    
    Ensures proper initialization order and integration between services.
    """
    
    _instance = None
    _services: Dict[str, Any] = {}
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._services = {}
            self._initialized = True
            logger.info("ServiceRegistry initialized")
    
    def get_user_service(self, db: Optional[Session] = None) -> UserService:
        """Get or create User Service with all integrations."""
        if 'user_service' not in self._services:
            db_session = db or SessionLocal()
            
            # Create services without circular dependency
            # Knowledge Graph first (no dependencies)
            if 'knowledge_graph' not in self._services:
                kg = TravelKnowledgeGraph(db=db_session)
                self._services['knowledge_graph'] = kg
            
            # Redistribution service (depends on KG only)
            if 'redistribution' not in self._services:
                self._services['redistribution'] = DemandRedistributionService(
                    db=db_session,
                    knowledge_graph=self._services['knowledge_graph'],
                    user_service=None  # Will be set later
                )
            
            # User service (depends on KG and redistribution)
            self._services['user_service'] = UserService(
                db=db_session,
                knowledge_graph=self._services['knowledge_graph'],
                redistribution_service=self._services['redistribution']
            )
            
            # Update redistribution with user service
            self._services['redistribution'].user_service = self._services['user_service']
            
            logger.info("UserService created with integrations")
        
        return self._services['user_service']
    
    def get_knowledge_graph(self, db: Optional[Session] = None) -> TravelKnowledgeGraph:
        """Get or create Knowledge Graph Service."""
        if 'knowledge_graph' not in self._services:
            db_session = db or SessionLocal()
            kg = TravelKnowledgeGraph(db=db_session)
            
            # Initialize graph with database data
            import asyncio
            asyncio.run(kg.initialize())
            
            self._services['knowledge_graph'] = kg
            logger.info("KnowledgeGraphService created and initialized")
        
        return self._services['knowledge_graph']
    
    def get_redistribution_service(self, db: Optional[Session] = None) -> DemandRedistributionService:
        """Get or create Demand Redistribution Service with integrations."""
        if 'redistribution' not in self._services:
            db_session = db or SessionLocal()
            
            # Create services without circular dependency
            # Knowledge Graph first (no dependencies)
            if 'knowledge_graph' not in self._services:
                kg = TravelKnowledgeGraph(db=db_session)
                self._services['knowledge_graph'] = kg
            
            # User service (depends on KG and redistribution)
            if 'user_service' not in self._services:
                self._services['user_service'] = UserService(
                    db=db_session,
                    knowledge_graph=self._services['knowledge_graph'],
                    redistribution_service=None  # Will be set later
                )
            
            # Redistribution service (depends on KG and user_service)
            self._services['redistribution'] = DemandRedistributionService(
                db=db_session,
                knowledge_graph=self._services['knowledge_graph'],
                user_service=self._services['user_service']
            )
            
            # Update user service with redistribution
            self._services['user_service'].redistribution = self._services['redistribution']
            
            logger.info("DemandRedistributionService created with integrations")
        
        return self._services['redistribution']
    
    def get_sync_agent(self, db: Optional[Session] = None) -> HeartbeatSyncAgent:
        """Get or create Sync Agent with Knowledge Graph integration."""
        db_session = db or SessionTransit()
        kg = self.get_knowledge_graph(db_session)
        
        return HeartbeatSyncAgent(db=db_session, knowledge_graph=kg)
    
    def get_sync_scheduler(self) -> HeartbeatScheduler:
        """Get or create Sync Scheduler with Knowledge Graph integration."""
        if 'scheduler' not in self._services:
            kg = self.get_knowledge_graph()
            self._services['scheduler'] = HeartbeatScheduler(knowledge_graph=kg)
            logger.info("HeartbeatScheduler created with Knowledge Graph integration")
        
        return self._services['scheduler']
    
    def get_station_departure_service(self, db: Optional[Session] = None) -> StationDepartureService:
        """Get or create Station Departure Service."""
        if 'station_departure' not in self._services:
            self._services['station_departure'] = StationDepartureService()
            logger.info("StationDepartureService created")
        
        return self._services['station_departure']
    
    def get_all_services(self) -> Dict[str, Any]:
        """Get all initialized services."""
        return self._services.copy()
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get status of all services."""
        status = {}
        
        for name, service in self._services.items():
            if hasattr(service, 'health_check'):
                try:
                    status[name] = service.health_check()
                except Exception as e:
                    status[name] = {"status": "error", "error": str(e)}
            else:
                status[name] = {"status": "active", "type": type(service).__name__}
        
        return status
    
    def shutdown(self):
        """Shutdown all services and cleanup."""
        # Stop scheduler if running
        if 'scheduler' in self._services:
            scheduler = self._services['scheduler']
            if scheduler.running:
                scheduler.stop()
        
        # Close database sessions
        for name, service in self._services.items():
            if hasattr(service, 'db') and service.db:
                try:
                    service.db.close()
                except:
                    pass
        
        self._services.clear()
        logger.info("ServiceRegistry shutdown complete")


# Global registry instance
registry = ServiceRegistry()


def get_user_service(db: Optional[Session] = None) -> UserService:
    """Convenience function to get User Service."""
    return registry.get_user_service(db)


def get_knowledge_graph(db: Optional[Session] = None) -> TravelKnowledgeGraph:
    """Convenience function to get Knowledge Graph."""
    return registry.get_knowledge_graph(db)


def get_redistribution_service(db: Optional[Session] = None) -> DemandRedistributionService:
    """Convenience function to get Demand Redistribution Service."""
    return registry.get_redistribution_service(db)


def get_sync_scheduler() -> HeartbeatScheduler:
    """Convenience function to get Sync Scheduler."""
    return registry.get_sync_scheduler()


def get_station_departure_service() -> StationDepartureService:
    """Convenience function to get Station Departure Service."""
    return registry.get_station_departure_service()


# ============================================================================
# Integration Workflows
# ============================================================================

async def run_full_sync_workflow():
    """
    Run full sync workflow integrating all services.
    
    1. Sync Service fetches station heartbeats
    2. Updates Knowledge Graph with station patterns
    3. Knowledge Graph updates route intelligence
    4. Demand Redistribution analyzes network
    5. User Service gets personalized recommendations
    """
    logger.info("🚀 Starting full sync workflow...")
    
    try:
        # Get services
        sync_agent = registry.get_sync_agent()
        kg = registry.get_knowledge_graph()
        redistribution = registry.get_redistribution_service()
        user_service = registry.get_user_service()
        
        # Step 1: Sync station heartbeats
        sync_results = await sync_agent.sync_hot_zones()
        logger.info(f"📡 Sync complete: {sync_results}")
        
        # Step 2: Analyze network demand
        await redistribution.analyze_network_demand()
        opportunities = await redistribution.identify_opportunities()
        logger.info(f"🎯 Found {len(opportunities)} redistribution opportunities")
        
        # Step 3: Get service status
        status = registry.get_service_status()
        logger.info(f"✅ All services healthy: {list(status.keys())}")
        
        return {
            "sync_results": sync_results,
            "opportunities": len(opportunities),
            "services": status
        }
        
    except Exception as e:
        logger.error(f"❌ Full sync workflow failed: {e}")
        raise


async def run_user_learning_workflow(user_id: str):
    """
    Run user learning workflow.
    
    1. Get user travel patterns from User Service
    2. Sync to Knowledge Graph
    3. Get personalized recommendations
    4. Get redistribution opportunities
    """
    logger.info(f"📚 Starting user learning workflow for {user_id}...")
    
    try:
        user_service = registry.get_user_service()
        kg = registry.get_knowledge_graph()
        redistribution = registry.get_redistribution_service()
        
        # Step 1: Analyze travel patterns
        pattern = user_service.analyze_travel_patterns(user_id)
        logger.info(f"📊 Analyzed {pattern.total_trips} trips for user {user_id}")
        
        # Step 2: Sync to Knowledge Graph
        await user_service.sync_user_to_knowledge_graph(user_id)
        logger.info(f"🧠 Synced user to Knowledge Graph")
        
        # Step 3: Get recommendations
        recommendations = await user_service.get_travel_recommendations(user_id)
        logger.info(f"💡 Generated {len(recommendations.get('recommendations', []))} recommendations")
        
        # Step 4: Get redistribution opportunities
        opportunities = await user_service.get_redistribution_opportunities(user_id)
        logger.info(f"🎯 Found {len(opportunities)} redistribution opportunities")
        
        return {
            "pattern": {
                "total_trips": pattern.total_trips,
                "preferred_routes": pattern.most_frequent_routes,
                "preferred_class": pattern.preferred_class
            },
            "recommendations": recommendations,
            "opportunities": opportunities
        }
        
    except Exception as e:
        logger.error(f"❌ User learning workflow failed: {e}")
        raise


def get_integration_health() -> Dict[str, Any]:
    """
    Get health status of all service integrations.
    """
    return registry.get_service_status()


# Export for external use
__all__ = [
    'ServiceRegistry',
    'registry',
    'get_user_service',
    'get_knowledge_graph',
    'get_redistribution_service',
    'get_sync_scheduler',
    'get_station_departure_service',
    'run_full_sync_workflow',
    'run_user_learning_workflow',
    'get_integration_health'
]
