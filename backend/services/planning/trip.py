import uuid
from sqlalchemy.orm import Session
from database.models import GroupTrip, TripParticipant
from schemas.trip_schemas import TripCreateSchema

class TripService:
    def __init__(self, db: Session):
        self.db = db

    def create_trip(self, payload: TripCreateSchema, user_id: str) -> GroupTrip:
        trip = GroupTrip(
            trip_id=f"trip_{uuid.uuid4().hex[:8]}",
            group_id=payload.group_id,
            origin=payload.origin,
            destination=payload.destination,
            travel_date=payload.travel_date,
            created_by=user_id
        )
        self.db.add(trip)
        self.db.commit()
        self.db.refresh(trip)

        creator = TripParticipant(trip_id=trip.id, user_id=user_id)
        self.db.add(creator)
        self.db.commit()

        return trip

    def leave_trip(self, trip_id: str, user_id: str):
        trip = self.db.query(GroupTrip).filter(GroupTrip.trip_id == trip_id).first()
        if not trip:
            raise ValueError("Trip not found.")

        participant = self.db.query(TripParticipant).filter(
            TripParticipant.trip_id == trip.id,
            TripParticipant.user_id == user_id
        ).first()

        if participant:
            self.db.delete(participant)
            self.db.commit()
            return True
        return False

    def get_trip(self, trip_id: str) -> GroupTrip:
        trip = self.db.query(GroupTrip).filter(GroupTrip.trip_id == trip_id).first()
        if not trip:
            raise ValueError("Trip not found.")
        return trip
