from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from api.dependencies import get_current_user
from services.trip_service import TripService
from schemas.trip_schemas import TripCreateSchema, TripResponseSchema

router = APIRouter(prefix="/v2/trips", tags=["trips"])

@router.post("/create", response_model=TripResponseSchema)
async def create_trip(
    payload: TripCreateSchema,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    service = TripService(db)
    return service.create_trip(payload, str(current_user.id))

@router.get("/{trip_id}", response_model=TripResponseSchema)
async def get_trip(
    trip_id: str,
    db: Session = Depends(get_db)
):
    service = TripService(db)
    try:
        return service.get_trip(trip_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/leave/{trip_id}")
async def leave_trip(
    trip_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    service = TripService(db)
    try:
        success = service.leave_trip(trip_id, str(current_user.id))
        if success:
            return {"success": True, "message": "Successfully left trip."}
        else:
            raise HTTPException(status_code=404, detail="Not a participant.")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
