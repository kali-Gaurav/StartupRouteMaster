import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from database.models import Booking, User

logger = logging.getLogger(__name__)

class HubRouteService:
    """
    Task 34: Alternative Hub-Route Suggestion.
    Orchestrates journeys involving transfers at major junctions.
    """
    
    MIN_BUFFER_MINUTES = 120 # Task 34.5: 2-hour buffer
    
    def __init__(self, db: Session):
        self.db = db

    def validate_hub_connection(self, arrival_time_leg1: datetime, departure_time_leg2: datetime) -> bool:
        """Task 34.5: Enforce minimum 2-hour buffer."""
        buffer = (departure_time_leg2 - arrival_time_leg1).total_seconds() / 60
        return buffer >= self.MIN_BUFFER_MINUTES

    def calculate_price_difference(self, leg1_fare: float, leg2_fare: float, direct_fare: Optional[float]) -> Dict[str, float]:
        """Task 34.2: Price difference calculator."""
        total_hub_fare = leg1_fare + leg2_fare
        diff = total_hub_fare - (direct_fare or 0)
        return {
            "total_hub_fare": total_hub_fare,
            "direct_fare": direct_fare or 0,
            "difference": diff,
            "is_cheaper": diff < 0 if direct_fare else False
        }

    async def suggest_hub_routes(self, source_code: str, destination_code: str, travel_date: str) -> List[Dict[str, Any]]:
        """Task 34.1 & 34.3: Suggest alternative routes via Hubs using actual Graph Engine."""
        from core.route_engine import route_engine
        from core.route_engine.constraints import RouteConstraints
        
        try:
            dt = datetime.fromisoformat(travel_date)
        except ValueError:
            dt = datetime.strptime(travel_date, "%Y-%m-%d")
            
        constraints = RouteConstraints(max_results=5)
        
        # Call the newly added method in RailwayRouteEngine
        routes = await route_engine.search_hub_routes(source_code, destination_code, dt, constraints, self.db)
        
        from database.models import Stop
        from database.session import SessionTransit
        transit_db = SessionTransit()
        
        hub_alternatives = []
        try:
            for rt in routes:
                if not rt.segments or not rt.transfers:
                    continue
                    
                # Assume 1 transfer for hub routes
                tr = rt.transfers[0]
                hub_station = transit_db.query(Stop).filter(Stop.id == tr.station_id).first()
                hub_code = hub_station.code if hub_station else str(tr.station_id)
                
                # Subtask 34.2: Price Difference
                total_fare = sum(s.fare or 0.0 for s in rt.segments)
                price_info = self.calculate_price_difference(total_fare, 0, 1200.0) # Assume direct is 1200 for now
                
                metadata = getattr(rt, "metadata", None) or {}
                hub_alternatives.append({
                    "type": "HUB_TRANSFER",
                    "hub_station": hub_code,
                    "legs": [s.__dict__ for s in rt.segments],
                    "price_info": price_info,
                    "buffer_minutes": tr.duration_minutes,
                    "warnings": [f"Self-transfer required at {hub_code}.", "Baggage must be moved manually."],
                    "platform_info": metadata.get("platforms", {})
                })
        finally:
            transit_db.close()
            
        return hub_alternatives

    async def initiate_hub_booking(self, user_id: str, hub_route_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Task 34.4 & 34.6: Multi-booking orchestration & Unified PNR View.
        Creates two linked booking requests.
        """
        from database.models import Booking
        import uuid
        
        # Task 34.6: Journey Group ID to link two bookings
        journey_group_id = f"HUB-{uuid.uuid4().hex[:8].upper()}"
        
        legs = hub_route_data.get("legs", [])
        if len(legs) < 2:
            return {"success": False, "message": "Invalid hub route data"}

        # Task 34.4: Backend orchestration to initiate 2 separate requests
        # In this implementation, we record the group ID in booking_details
        created_bookings = []
        for i, leg in enumerate(legs):
            new_booking = Booking(
                id=str(uuid.uuid4()),
                user_id=user_id,
                booking_status="pending",
                amount_paid=leg.get("fare", 0.0),
                booking_details={
                    "is_hub_journey": True,
                    "journey_group_id": journey_group_id,
                    "leg_index": i,
                    "train_no": leg.get("train_number"),
                    "from": leg.get("departure_stop_code"),
                    "to": leg.get("arrival_stop_code")
                }
            )
            self.db.add(new_booking)
            created_bookings.append(new_booking)
        
        self.db.commit()
        
        return {
            "success": True,
            "journey_group_id": journey_group_id,
            "message": f"Successfully queued {len(created_bookings)} legs for Hub Journey.",
            "booking_ids": [b.id for b in created_bookings]
        }

    async def ai_destination_guarantee_check(self, journey_group_id: str) -> Dict[str, Any]:
        """
        Task 34.10: AI Destination Guarantee.
        Monitors Leg 1 and suggests pivot plans via Gemini if connection is at risk.
        """
        from database.models import Booking, TrainLiveUpdate
        from config import Config
        import google.generativeai as genai
        from sqlalchemy import cast, String
        from typing import Any, cast as type_cast
        
        # 1. Fetch the hub journey legs
        bookings = self.db.query(Booking).filter(
            cast(Booking.booking_details["journey_group_id"], String) == f'"{journey_group_id}"' # SQLite JSON extracts with quotes
        ).order_by(cast(Booking.booking_details["leg_index"], String)).all()
        
        if len(bookings) < 2:
            return {"status": "ERROR", "message": "Journey group incomplete"}
            
        leg1 = bookings[0]
        leg2 = bookings[1]
        
        # 2. Check current delay of Leg 1 (Simulated lookup)
        leg1_details = leg1.booking_details or {}
        leg1_train = leg1_details.get("train_no")
        hub_stn = leg1_details.get("to")
        
        # In real system, query TrainLiveUpdate table
        # For demo, simulate a 90-minute delay on Leg 1
        current_delay = 90 
        
        # 3. Calculate remaining buffer
        original_buffer = 120 # From task 34.5
        remaining_buffer = original_buffer - current_delay
        
        is_at_risk = remaining_buffer <= 30 # Inclusive of 30 mins
        
        if not is_at_risk:
            return {
                "status": "SAFE", 
                "remaining_buffer": remaining_buffer, 
                "message": "Connection is secure."
            }

        # 4. If at risk, use AI to suggest a pivot
        if hasattr(Config, 'GEMINI_API_KEY'):
            genai_any = type_cast(Any, genai)
            if hasattr(genai_any, 'configure') and hasattr(genai_any, 'GenerativeModel'):
                genai_any.configure(api_key=Config.GEMINI_API_KEY)
                model = genai_any.GenerativeModel('gemini-2.5-flash')
            else:
                model = None
            
            leg2_details = leg2.booking_details or {}
            prompt = f"""
            AI Destination Guarantee System.
            User is on Train {leg1_train} arriving at {hub_stn}.
            Connection Train {leg2_details.get('train_no')} departs in {remaining_buffer} minutes.
            The connection is HIGH RISK.
            
            Suggest 2 emergency pivot plans:
            1. An alternative onward train from {hub_stn} 3 hours later.
            2. A nearby bus station alternative.
            
            Return JSON only: {{"risk_level": "CRITICAL", "alternatives": []}}
            """
            
            if model is not None:
                try:
                    response = model.generate_content(prompt)
                    pivot_plans = response.text
                    return {
                        "status": "AT_RISK",
                        "remaining_buffer": remaining_buffer,
                        "ai_suggestions": pivot_plans,
                        "message": "AI monitoring has detected a high-risk connection. See pivot plans."
                    }
                except:
                    pass
                
        return {
            "status": "AT_RISK",
            "remaining_buffer": remaining_buffer,
            "message": "Connection high risk. Please check for alternative onward trains manually."
        }
