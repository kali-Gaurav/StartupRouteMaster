
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import date
from .routing import Route, RouteConstraints
from .common import PaginationMetadata

class SearchRequest(BaseModel):
    source: str
    destination: str
    travel_date: date
    budget: Optional[str] = None
    page: int = 1
    limit: int = 15
    cursor: Optional[float] = None
    quota: str = "GN"
    persona: Optional[str] = None

class SearchResponse(BaseModel):
    routes: List[Route]
    pagination: Optional[PaginationMetadata] = None
    surge_active: bool = False
    metadata: Dict[str, Any] = {}
