from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List

class TripCreateSchema(BaseModel):
    origin: str = Field(..., min_length=3)
    destination: str = Field(..., min_length=3)
    travel_date: datetime = Field(...)
    group_id: Optional[str] = Field(None)

class TripResponseSchema(BaseModel):
    id: str
    trip_id: str
    origin: str
    destination: str
    travel_date: datetime
    created_by: str
    is_active: bool
