"""
Knowledge Graph API Endpoints

Provides REST API for:
- Graph persistence and recovery
- Learning from data
- Querying intelligence
- Getting recommendations
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, List
from datetime import datetime
from pydantic import BaseModel

from database.session import get_db
from services.knowledge_graph_service import get_knowledge_graph, TravelKnowledgeGraph
from services.knowledge_graph_persistence import get_knowledge_graph_persistence

router = APIRouter(prefix="/api/knowledge-graph", tags=["Knowledge Graph"])


class LearnFromBookingRequest(BaseModel):
    """Request to learn from booking data"""
    user_id: str
    source: str
    destination: str
    travel_date: str
    booking_class: str = "SL"
    price: float
    cancelled: bool = False


class LearnFromSearchRequest(BaseModel):
    """Request to learn from search data"""
    user_id: str = None
    source: str
    destination: str
    travel_date: str
    search_timestamp: str = None


class QueryRequest(BaseModel):
    """Request to query knowledge graph"""
    query_type: str  # route_intelligence, similar_users, recommendations
    parameters: Dict[str, Any]


class GraphSaveRequest(BaseModel):
    """Request to save graph snapshot"""
    description: str = ""


class GraphLoadRequest(BaseModel):
    """Request to load graph snapshot"""
    snapshot_id: str = None  # None = latest


@router.post("/learn/booking")
async def learn_from_booking(
    request: LearnFromBookingRequest,
    db=Depends(get_db)
):
    """
    Learn from booking data.
    
    Updates:
    - Route popularity
    - User preferences
    - Cancellation patterns
    """
    try:
        kg = get_knowledge_graph(db)
        
        booking_data = {
            "source": request.source,
            "destination": request.destination,
            "travel_date": datetime.fromisoformat(request.travel_date) if isinstance(request.travel_date, str) else request.travel_date,
            "booking_class": request.booking_class,
            "price": request.price,
            "cancelled": request.cancelled
        }
        
        await kg.learn_from_booking(booking_data, request.user_id)
        
        return {
            "status": "success",
            "message": "Learned from booking",
            "user_id": request.user_id
        }
        
    except Exception as e:
        logger.error(f"Learning from booking error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/learn/search")
async def learn_from_search(
    request: LearnFromSearchRequest,
    db=Depends(get_db)
):
    """
    Learn from search data.
    
    Updates:
    - Route demand patterns
    - Search-to-booking conversion
    """
    try:
        kg = get_knowledge_graph(db)
        
        search_data = {
            "src": request.source,
            "dest": request.destination,
            "travel_date": datetime.fromisoformat(request.travel_date) if isinstance(request.travel_date, str) else request.travel_date,
            "timestamp": datetime.fromisoformat(request.search_timestamp) if request.search_timestamp else datetime.utcnow()
        }
        
        await kg.learn_from_search(search_data, request.user_id)
        
        return {
            "status": "success",
            "message": "Learned from search",
            "source": request.source,
            "destination": request.destination
        }
        
    except Exception as e:
        logger.error(f"Learning from search error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/query")
async def query_knowledge_graph(
    request: QueryRequest,
    db=Depends(get_db)
):
    """
    Query knowledge graph for intelligence.
    
    Query types:
    - route_intelligence: Get intelligence for a route
    - similar_users: Get users with similar patterns
    - recommendations: Get personalized recommendations
    """
    try:
        kg = get_knowledge_graph(db)
        
        if request.query_type == "route_intelligence":
            source = request.parameters.get("source")
            destination = request.parameters.get("destination")
            intelligence = kg.get_route_intelligence(source, destination)
            return {
                "query_type": "route_intelligence",
                "source": source,
                "destination": destination,
                "intelligence": intelligence
            }
        
        elif request.query_type == "similar_users":
            user_id = request.parameters.get("user_id")
            limit = request.parameters.get("limit", 5)
            similar = await kg.get_similar_users(user_id, limit)
            return {
                "query_type": "similar_users",
                "user_id": user_id,
                "similar_users": similar
            }
        
        elif request.query_type == "recommendations":
            user_id = request.parameters.get("user_id")
            preferences = request.parameters.get("preferences", {})
            recommendations = await kg.get_personalized_recommendations(user_id, preferences)
            return {
                "query_type": "recommendations",
                "user_id": user_id,
                "recommendations": recommendations
            }
        
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown query type: {request.query_type}"
            )
        
    except Exception as e:
        logger.error(f"Query error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/save")
async def save_graph(
    request: GraphSaveRequest,
    db=Depends(get_db)
):
    """
    Save knowledge graph snapshot to database.
    
    Creates a backup of the current graph state.
    """
    try:
        kg = get_knowledge_graph(db)
        persistence = get_knowledge_graph_persistence(db)
        
        snapshot_id = await persistence.save_graph(kg, request.description)
        
        return {
            "status": "success",
            "snapshot_id": snapshot_id,
            "node_count": len(kg.graph.nodes),
            "edge_count": len(kg.graph.edges),
            "description": request.description
        }
        
    except Exception as e:
        logger.error(f"Save error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/load")
async def load_graph(
    request: GraphLoadRequest,
    db=Depends(get_db)
):
    """
    Load knowledge graph from database.
    
    Restores a previous graph state.
    """
    try:
        persistence = get_knowledge_graph_persistence(db)
        
        graph = await persistence.load_graph(request.snapshot_id)
        
        if not graph:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Graph snapshot not found"
            )
        
        return {
            "status": "success",
            "snapshot_id": request.snapshot_id,
            "node_count": len(graph.graph.nodes),
            "edge_count": len(graph.graph.edges)
        }
        
    except Exception as e:
        logger.error(f"Load error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/history")
async def get_snapshot_history(
    limit: int = 10,
    db=Depends(get_db)
):
    """
    Get history of graph snapshots.
    """
    try:
        persistence = get_knowledge_graph_persistence(db)
        history = persistence.get_snapshot_history(limit)
        
        return {
            "snapshots": history
        }
        
    except Exception as e:
        logger.error(f"History error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/stats")
async def get_graph_stats(
    db=Depends(get_db)
):
    """
    Get knowledge graph statistics.
    """
    try:
        kg = get_knowledge_graph(db)
        
        return {
            "node_count": len(kg.graph.nodes),
            "edge_count": len(kg.graph.edges),
            "station_patterns": len(kg.station_patterns),
            "route_patterns": len(kg.route_patterns),
            "user_preferences": len(kg.user_preferences)
        }
        
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# Import logger at module level
import logging
logger = logging.getLogger(__name__)
