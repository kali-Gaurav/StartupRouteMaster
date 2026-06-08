from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from database.session import get_db
from database.models import User, SOSEvent, EmergencyContact
from services.sos_service import SOSService
from utils.responses import success_response, v3_response, error_response
from pydantic import BaseModel

router = APIRouter(prefix="/v3/sos", tags=["Safety & SOS"])

class SOSRequest(BaseModel):
    user_id: str
    lat: float
    lng: float
    category: str = "MANUAL"
    trip_data: Optional[Dict] = None

class HeartbeatRequest(BaseModel):
    user_id: str
    journey_id: str
    station_code: str
    next_eta: str # ISO Format

class ContactCreate(BaseModel):
    user_id: str
    name: str
    phone: str
    relation: str

@router.post("/trigger")
async def trigger_sos(req: SOSRequest, db: Session = Depends(get_db)):
    """
    Immediate SOS Trigger - Point 20.
    """
    sos_service = SOSService(db)
    event_id = await sos_service.trigger_sos(
        user_id=req.user_id,
        lat=req.lat,
        lng=req.lng,
        category=req.category,
        trip_data=req.trip_data
    )
    return v3_response(
        data={"event_id": event_id},
        status="ACTIVE",
        metadata={"message": "Emergency services and contacts notified."}
    )

@router.post("/heartbeat")
async def update_heartbeat(req: HeartbeatRequest, db: Session = Depends(get_db)):
    """
    Periodic Check-in for 'Guardian' mode.
    """
    from datetime import datetime
    try:
        eta_dt = datetime.fromisoformat(req.next_eta)
    except:
        raise HTTPException(status_code=400, detail="Invalid ETA format. Use ISO format.")

    sos_service = SOSService(db)
    await sos_service.update_heartbeat(
        user_id=req.user_id,
        journey_id=req.journey_id,
        station_code=req.station_code,
        next_eta=eta_dt
    )
    return success_response("Guardian heartbeat updated.")

@router.get("/contacts/{user_id}")
async def get_contacts(user_id: str, db: Session = Depends(get_db)):
    contacts = db.query(EmergencyContact).filter(EmergencyContact.user_id == user_id).all()
    return success_response({
        "contacts": [{"name": c.name, "phone": c.phone, "relation": c.relation} for c in contacts]
    })

@router.post("/contacts")
async def add_contact(req: ContactCreate, db: Session = Depends(get_db)):
    contact = EmergencyContact(
        user_id=req.user_id,
        name=req.name,
        phone=req.phone,
        relation=req.relation
    )
    db.add(contact)
    db.commit()
    return success_response({"contact_id": contact.id})

@router.get("/status/{event_id}")
async def get_sos_status(event_id: str, db: Session = Depends(get_db)):
    event = db.query(SOSEvent).filter(SOSEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="SOS Event not found")
    
    return success_response({
        "status": event.status,
        "triggered_at": event.triggered_at,
        "location": {"lat": event.lat, "lng": event.lng},
        "telemetry_count": len(event.telemetry)
    })
