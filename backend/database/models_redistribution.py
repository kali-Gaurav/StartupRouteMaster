"""
Database Models for Redistribution and Knowledge Graph Features

Extends the core models with:
- Redistribution offers and opportunities
- Knowledge graph nodes and edges
- ML model metadata
- Agent workflow definitions
"""

from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from database.models import Base


class RedistributionOpportunity(Base):
    """
    Tracks redistribution opportunities in the network.
    
    Identifies routes where demand/supply is imbalanced
    and passengers can be redistributed.
    """
    __tablename__ = "redistribution_opportunities"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    opportunity_id = Column(String(36), unique=True, nullable=False, index=True)
    
    # Source route (high demand)
    source_route_id = Column(String(100), nullable=False, index=True)
    source_station = Column(String(10), nullable=False)
    destination_station = Column(String(10), nullable=False)
    travel_date = Column(DateTime, nullable=False)
    current_bookings = Column(Integer, nullable=False)
    capacity = Column(Integer, nullable=False)
    demand_score = Column(Float, nullable=False)  # 0.0 - 1.0
    
    # Target route (low demand)
    target_route_id = Column(String(100), nullable=False, index=True)
    target_station = Column(String(10), nullable=False)
    target_destination = Column(String(10), nullable=False)
    target_capacity = Column(Integer, nullable=False)
    target_demand_score = Column(Float, nullable=False)
    
    # Opportunity details
    passengers_needed = Column(Integer, nullable=False)
    incentive_range_min = Column(Float, nullable=False)
    incentive_range_max = Column(Float, nullable=False)
    time_advantage = Column(Integer, nullable=True)  # minutes
    
    # Status
    status = Column(String(20), default="identified")  # identified, active, completed, expired
    offers_generated = Column(Integer, default=0)
    offers_accepted = Column(Integer, default=0)
    
    # Timestamps
    identified_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    offers = relationship("RedistributionOffer", back_populates="opportunity")


class RedistributionOffer(Base):
    """
    Individual offer to a passenger for redistribution.
    
    Generated when a passenger on a high-demand route
    is offered an alternative route with incentives.
    """
    __tablename__ = "redistribution_offers"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    offer_id = Column(String(36), unique=True, nullable=False, index=True)
    opportunity_id = Column(Integer, ForeignKey("redistribution_opportunities.id"), nullable=False)
    
    # Passenger and booking
    passenger_id = Column(String(100), nullable=False, index=True)
    original_booking_id = Column(String(100), nullable=False, index=True)
    
    # Original route details
    original_source = Column(String(10), nullable=False)
    original_destination = Column(String(10), nullable=False)
    original_train = Column(String(20), nullable=False)
    original_date = Column(DateTime, nullable=False)
    original_fare = Column(Float, nullable=False)
    
    # Alternative route details
    alternative_source = Column(String(10), nullable=False)
    alternative_destination = Column(String(10), nullable=False)
    alternative_train = Column(String(20), nullable=False)
    alternative_date = Column(DateTime, nullable=False)
    alternative_fare = Column(Float, nullable=False)
    
    # Offer details
    incentive_amount = Column(Float, nullable=False)
    time_difference = Column(Integer, nullable=True)  # minutes (positive = faster)
    comfort_improvement = Column(Float, nullable=True)  # score
    
    # Status
    status = Column(String(20), default="pending")  # pending, accepted, rejected, expired
    offered_at = Column(DateTime, default=datetime.utcnow)
    responded_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=False)
    executed_at = Column(DateTime, nullable=True)
    
    # New booking (if accepted)
    new_booking_id = Column(String(100), nullable=True, index=True)
    
    # Passenger flexibility score (used for targeting)
    passenger_flexibility = Column(Float, nullable=True)
    price_sensitivity = Column(Float, nullable=True)
    
    # Relationships
    opportunity = relationship("RedistributionOpportunity", back_populates="offers")


class IncentiveCredit(Base):
    """
    Tracks incentive credits applied to user accounts.
    
    Credits can be from redistribution offers, promotions, etc.
    """
    __tablename__ = "incentive_credits"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    credit_id = Column(String(36), unique=True, nullable=False, index=True)
    
    # User
    user_id = Column(String(100), nullable=False, index=True)
    
    # Credit details
    amount = Column(Float, nullable=False)
    credit_type = Column(String(50), nullable=False)  # redistribution, promotion, referral
    description = Column(Text, nullable=True)
    
    # Related booking
    booking_id = Column(String(100), nullable=True, index=True)
    
    # Validity
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    used_at = Column(DateTime, nullable=True)
    
    # Status
    status = Column(String(20), default="active")  # active, used, expired
    used_amount = Column(Float, default=0.0)


class KnowledgeGraphSnapshot(Base):
    """
    Snapshot of knowledge graph for backup/recovery.
    
    Stores complete graph state at point in time.
    """
    __tablename__ = "knowledge_graph_snapshots"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(String(36), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False)
    
    # Graph statistics
    node_count = Column(Integer, nullable=False)
    edge_count = Column(Integer, nullable=False)
    
    # Serialized data
    nodes_data = Column(Text, nullable=False)
    edges_data = Column(Text, nullable=False)
    station_patterns = Column(Text, nullable=True)
    route_patterns = Column(Text, nullable=True)
    user_preferences = Column(Text, nullable=True)
    
    # Metadata
    version = Column(String(20), default="1.0")
    description = Column(Text, nullable=True)


class KnowledgeGraphNode(Base):
    """
    Individual node in knowledge graph.
    
    Represents stations, routes, transfers, etc.
    """
    __tablename__ = "knowledge_graph_nodes"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    node_id = Column(String(100), unique=True, nullable=False, index=True)
    node_type = Column(String(50), nullable=False)  # station, route, transfer, user
    
    # Node attributes (JSON)
    attributes = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Versioning
    version = Column(Integer, default=1)


class KnowledgeGraphEdge(Base):
    """
    Edge between nodes in knowledge graph.
    
    Represents relationships like routes, transfers, preferences.
    """
    __tablename__ = "knowledge_graph_edges"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(String(100), nullable=False, index=True)
    target_id = Column(String(100), nullable=False, index=True)
    edge_type = Column(String(50), nullable=False)  # route, transfer, preference, similar
    
    # Edge weight/attributes
    weight = Column(Float, default=1.0)
    attributes = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MLModelMetadata(Base):
    """
    Metadata for trained ML models.
    
    Tracks model versions, performance metrics, and training data.
    """
    __tablename__ = "ml_model_metadata"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(String(100), unique=True, nullable=False, index=True)
    model_type = Column(String(50), nullable=False)  # delay, cancellation, demand
    
    # Versioning
    version = Column(String(50), nullable=False)
    parent_version = Column(String(50), nullable=True)
    
    # Training details
    trained_at = Column(DateTime, default=datetime.utcnow)
    training_data_days = Column(Integer, nullable=False)
    sample_count = Column(Integer, nullable=False)
    
    # Performance metrics
    metrics = Column(JSON, nullable=True)  # mae, accuracy, precision, recall, f1
    
    # Model location
    model_path = Column(String(500), nullable=False)
    feature_names = Column(JSON, nullable=True)
    hyperparameters = Column(JSON, nullable=True)
    
    # Status
    status = Column(String(20), default="training")  # training, ready, deprecated
    deployed_at = Column(DateTime, nullable=True)
    deprecated_at = Column(DateTime, nullable=True)


class AgentWorkflowDefinition(Base):
    """
    Definition of agent workflows.
    
    Defines multi-step workflows that agents execute.
    """
    __tablename__ = "agent_workflow_definitions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # Workflow definition (JSON)
    tasks = Column(JSON, nullable=False)  # Task definitions
    parallel_tasks = Column(JSON, nullable=True)  # Task IDs that can run in parallel
    input_schema = Column(JSON, nullable=True)
    output_schema = Column(JSON, nullable=True)
    
    # Metadata
    version = Column(String(20), default="1.0")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Status
    is_active = Column(Boolean, default=True)


class AgentWorkflowExecution(Base):
    """
    Tracks workflow execution instances.
    
    Records workflow runs for monitoring and debugging.
    """
    __tablename__ = "agent_workflow_executions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    execution_id = Column(String(36), unique=True, nullable=False, index=True)
    workflow_id = Column(String(100), nullable=False, index=True)
    
    # Input/Output
    input_context = Column(JSON, nullable=True)
    output_context = Column(JSON, nullable=True)
    
    # Task results (JSON)
    task_results = Column(JSON, nullable=True)
    
    # Execution status
    status = Column(String(20), default="pending")  # pending, running, completed, failed
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    
    # Error tracking
    error = Column(Text, nullable=True)


# Export for external use
__all__ = [
    'RedistributionOpportunity',
    'RedistributionOffer',
    'IncentiveCredit',
    'KnowledgeGraphSnapshot',
    'KnowledgeGraphNode',
    'KnowledgeGraphEdge',
    'MLModelMetadata',
    'AgentWorkflowDefinition',
    'AgentWorkflowExecution'
]