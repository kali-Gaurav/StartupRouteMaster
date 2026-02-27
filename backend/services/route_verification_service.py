"""
Route Verification Service
Intelligent service for verifying routes during unlock payment flow.

Follows prompt.md framework:
- Functional Correctness: Validates all inputs, handles edge cases
- Performance: Caches results, minimizes API calls
- Error Handling: Graceful degradation, fallback strategies
- API Optimization: Smart caching, budget-aware
"""

import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session

from core.route_engine.data_provider import DataProvider
from database.models import Trip, StopTime, Stop, Segment, Station

logger = logging.getLogger(__name__)


class RouteVerificationService:
    """
    Service for verifying route information during unlock payment.
    
    Responsibilities:
    1. Extract route information (train number, stations) from various sources
    2. Verify seat availability via RapidAPI (with caching)
    3. Verify fare via RapidAPI (with caching)
    4. Handle failures gracefully with database fallback
    5. Optimize API usage through intelligent caching
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.data_provider = DataProvider()
        self.data_provider.detect_available_features()
    
    async def verify_route_for_unlock(
        self,
        route_id: str,
        travel_date: str,
        train_number: Optional[str] = None,
        from_station_code: Optional[str] = None,
        to_station_code: Optional[str] = None,
        source_station_name: Optional[str] = None,
        destination_station_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Verify route for unlock payment flow.
        
        Args:
            route_id: Route identifier (can be journey_id, route UUID, etc.)
            travel_date: Travel date in YYYY-MM-DD format
            train_number: Optional train number (if provided, use directly)
            from_station_code: Optional source station code (if provided, use directly)
            to_station_code: Optional destination station code (if provided, use directly)
            source_station_name: Optional source station name (for lookup)
            destination_station_name: Optional destination station name (for lookup)
        
        Returns:
            Dict with verification results:
            {
                "success": bool,
                "verification": {
                    "sl_availability": {...},
                    "ac3_availability": {...},
                    "sl_fare": {...},
                    "ac3_fare": {...}
                },
                "route_info": {
                    "train_number": str,
                    "from_station_code": str,
                    "to_station_code": str
                },
                "warnings": List[str],
                "api_calls_made": int
            }
        """
        warnings = []
        api_calls_made = 0
        
        # Step 1: Extract route information
        route_info = await self._extract_route_info(
            route_id=route_id,
            train_number=train_number,
            from_station_code=from_station_code,
            to_station_code=to_station_code,
            source_station_name=source_station_name,
            destination_station_name=destination_station_name
        )
        
        if not route_info["success"]:
            return {
                "success": False,
                "error": route_info.get("error", "Failed to extract route information"),
                "verification": {},
                "route_info": {},
                "warnings": warnings,
                "api_calls_made": api_calls_made
            }
        
        train_no = route_info["train_number"]
        from_stn = route_info["from_station_code"]
        to_stn = route_info["to_station_code"]
        
        if not train_no or not from_stn or not to_stn:
            warnings.append("Incomplete route information - verification may use database fallback")
        
        # Step 2: Parse travel date
        try:
            travel_date_obj = datetime.strptime(travel_date, "%Y-%m-%d").date()
            travel_datetime = datetime.combine(travel_date_obj, datetime.min.time())
        except ValueError:
            return {
                "success": False,
                "error": f"Invalid travel date format: {travel_date}. Expected YYYY-MM-DD",
                "verification": {},
                "route_info": route_info,
                "warnings": warnings,
                "api_calls_made": api_calls_made
            }
        
        # Step 3: Verify seat availability and fare (with caching)
        verification_results = {}
        
        # Verify SL (Sleeper) - Seat Availability
        sl_availability = await self._verify_seat_availability(
            train_number=train_no,
            from_station=from_stn,
            to_station=to_stn,
            travel_date=travel_datetime,
            coach_preference="SLEEPER",
            trip_id=route_info.get("trip_id")
        )
        # Count API calls (not cache hits)
        if sl_availability.get("source") == "rapidapi":
            api_calls_made += 1
        verification_results["sl_availability"] = sl_availability
        
        # Verify 3AC - Seat Availability
        ac3_availability = await self._verify_seat_availability(
            train_number=train_no,
            from_station=from_stn,
            to_station=to_stn,
            travel_date=travel_datetime,
            coach_preference="AC_THREE_TIER",
            trip_id=route_info.get("trip_id")
        )
        # Count API calls (not cache hits)
        if ac3_availability.get("source") == "rapidapi":
            api_calls_made += 1
        verification_results["ac3_availability"] = ac3_availability
        
        # Verify SL Fare
        sl_fare = await self._verify_fare(
            train_number=train_no,
            from_station=from_stn,
            to_station=to_stn,
            coach_preference="SLEEPER",
            segment_id=route_info.get("segment_id")
        )
        # Count API calls (not cache hits)
        if sl_fare.get("source") == "rapidapi":
            api_calls_made += 1
        verification_results["sl_fare"] = sl_fare
        
        # Verify 3AC Fare
        ac3_fare = await self._verify_fare(
            train_number=train_no,
            from_station=from_stn,
            to_station=to_stn,
            coach_preference="AC_THREE_TIER",
            segment_id=route_info.get("segment_id")
        )
        # Count API calls (not cache hits)
        if ac3_fare.get("source") == "rapidapi":
            api_calls_made += 1
        verification_results["ac3_fare"] = ac3_fare
        
        # Check if any verification failed critically
        critical_failures = []
        if sl_availability.get("status") == "error":
            critical_failures.append("SL availability check failed")
        if ac3_availability.get("status") == "error":
            critical_failures.append("3AC availability check failed")
        
        # Note: Fare failures are not critical - we can proceed with database fare
        if sl_fare.get("status") == "error":
            warnings.append("SL fare verification failed - using database fare")
        if ac3_fare.get("status") == "error":
            warnings.append("3AC fare verification failed - using database fare")
        
        return {
            "success": len(critical_failures) == 0,
            "verification": verification_results,
            "route_info": {
                "train_number": train_no,
                "from_station_code": from_stn,
                "to_station_code": to_stn,
                "from_station_name": route_info.get("from_station_name"),
                "to_station_name": route_info.get("to_station_name")
            },
            "warnings": warnings,
            "api_calls_made": api_calls_made,
            "errors": critical_failures if critical_failures else None
        }
    
    async def _extract_route_info(
        self,
        route_id: str,
        train_number: Optional[str] = None,
        from_station_code: Optional[str] = None,
        to_station_code: Optional[str] = None,
        source_station_name: Optional[str] = None,
        destination_station_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract route information from various sources.
        
        Priority:
        1. Direct parameters (train_number, from_station_code, to_station_code)
        2. Journey ID format (rt_{trip_id}_{timestamp})
        3. Database lookup via route_id
        4. Station name lookup
        """
        result = {
            "success": False,
            "train_number": None,
            "from_station_code": None,
            "to_station_code": None,
            "from_station_name": None,
            "to_station_name": None,
            "trip_id": None,
            "segment_id": None
        }
        
        # Priority 1: Use direct parameters if provided
        if train_number and from_station_code and to_station_code:
            result.update({
                "success": True,
                "train_number": train_number,
                "from_station_code": from_station_code.upper(),
                "to_station_code": to_station_code.upper()
            })
            
            # Lookup station names if codes provided
            from_stop = self.db.query(Stop).filter(Stop.code == from_station_code.upper()).first()
            to_stop = self.db.query(Stop).filter(Stop.code == to_station_code.upper()).first()
            
            if from_stop:
                result["from_station_name"] = from_stop.name
            if to_stop:
                result["to_station_name"] = to_stop.name
            
            # Try to find trip_id and segment_id for better verification
            if from_stop and to_stop:
                # Find segment matching this route. 
                # Note: Segments usually link to Station.id (UUID), whereas Stop has internal Integer id.
                # We try to find Station by name first.
                from_station = self.db.query(Station).filter(Station.name == from_stop.name).first()
                to_station = self.db.query(Station).filter(Station.name == to_stop.name).first()
                
                source_id = from_station.id if from_station else str(from_stop.id)
                dest_id = to_station.id if to_station else str(to_stop.id)

                segment = self.db.query(Segment).filter(
                    Segment.source_station_id == source_id,
                    Segment.dest_station_id == dest_id
                ).first()
                
                if segment:
                    result["segment_id"] = segment.id
                    if segment.trip_id:
                        result["trip_id"] = segment.trip_id
                        
                        # Also try to get trip to verify train_number matches
                        trip = segment.trip if hasattr(segment, 'trip') else None
                        if not trip and segment.trip_id:
                            trip = self.db.query(Trip).filter(Trip.id == segment.trip_id).first()
                        
                        if trip and hasattr(trip, 'route') and trip.route:
                            # Verify train_number matches route
                            route_train_no = getattr(trip.route, 'short_name', None) or getattr(trip.route, 'route_id', None)
                            if route_train_no and route_train_no != train_number:
                                # Log mismatch but use provided train_number
                                logger.warning(
                                    f"Train number mismatch: provided={train_number}, "
                                    f"route={route_train_no}"
                                )
            
            return result
        
        # Priority 2: Try journey_id format (rt_{trip_id}_{timestamp})
        if route_id.startswith("rt_"):
            parts = route_id.split("_")
            if len(parts) >= 2:
                trip_id_str = parts[1]
                try:
                    trip_id = int(trip_id_str)
                    trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
                    if trip:
                        # Get train number - Trip model doesn't have train_number field directly
                        # Train number is typically stored in route.short_name or extracted from trip_id
                        train_no = None
                        
                        # Method 1: Get from route.short_name (route_id often contains train number)
                        if hasattr(trip, 'route') and trip.route:
                            route = trip.route
                            train_no = getattr(route, 'short_name', None) or getattr(route, 'route_id', None)
                        
                        # Method 2: Try to extract from trip_id if it's in format "train_number_date_stations"
                        trip_id_str = getattr(trip, 'trip_id', None)
                        if not train_no and trip_id_str:
                            # trip_id format might be: "12951_20260215_NDLS-MMCT"
                            parts = trip_id_str.split('_')
                            if parts and parts[0].isdigit() and len(parts[0]) == 5:
                                train_no = parts[0]  # First part is likely train number
                        
                        # Method 3: Query TrainState if available
                        if not train_no:
                            try:
                                from database.models import TrainState
                                train_state = self.db.query(TrainState).filter(
                                    TrainState.trip_id == trip.id
                                ).first()
                                if train_state:
                                    train_no = train_state.train_number
                            except (ImportError, AttributeError):
                                pass
                        
                        # Last resort: use trip_id if numeric (5 digits = train number format)
                        if not train_no and trip_id_str and trip_id_str.isdigit() and len(trip_id_str) == 5:
                            train_no = trip_id_str
                        
                        # Get first and last stops
                        stop_times = self.db.query(StopTime).filter(
                            StopTime.trip_id == trip.id
                        ).order_by(StopTime.stop_sequence).all()
                        
                        if stop_times:
                            first_stop_time = stop_times[0]
                            last_stop_time = stop_times[-1]
                            
                            from_stop = self.db.query(Stop).filter(
                                Stop.id == first_stop_time.stop_id
                            ).first()
                            to_stop = self.db.query(Stop).filter(
                                Stop.id == last_stop_time.stop_id
                            ).first()
                            
                            if from_stop and to_stop and train_no:
                                result.update({
                                    "success": True,
                                    "train_number": train_no,
                                    "from_station_code": from_stop.code,
                                    "to_station_code": to_stop.code,
                                    "from_station_name": from_stop.name,
                                    "to_station_name": to_stop.name,
                                    "trip_id": trip.id
                                })
                                
                                # Find segment
                                segment = self.db.query(Segment).filter(
                                    Segment.trip_id == trip.id
                                ).first()
                                if segment:
                                    result["segment_id"] = segment.id
                                
                                return result
                except (ValueError, AttributeError) as e:
                    logger.warning(f"Failed to parse journey_id {route_id}: {e}")
        
        # Priority 3: Station name lookup (if provided)
        if source_station_name and destination_station_name:
            from_stop = self.db.query(Stop).filter(
                Stop.name.ilike(f"%{source_station_name}%")
            ).first()
            to_stop = self.db.query(Stop).filter(
                Stop.name.ilike(f"%{destination_station_name}%")
            ).first()
            
            if from_stop and to_stop:
                result.update({
                    "success": True,
                    "from_station_code": from_stop.code,
                    "to_station_code": to_stop.code,
                    "from_station_name": from_stop.name,
                    "to_station_name": to_stop.name
                })
                # Note: train_number still missing, will use database fallback
        
        # If we still don't have success, return error
        if not result["success"]:
            result["error"] = f"Could not extract route information from route_id: {route_id}"
            logger.warning(result["error"])
        
        return result
    
    async def _verify_seat_availability(
        self,
        train_number: Optional[str],
        from_station: Optional[str],
        to_station: Optional[str],
        travel_date: datetime,
        coach_preference: str,
        trip_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Verify seat availability with fallback."""
        if not train_number or not from_station or not to_station:
            # Fallback to database
            if trip_id:
                return await self.data_provider.verify_seat_availability_unified(
                    trip_id=trip_id,
                    travel_date=travel_date,
                    coach_preference=coach_preference
                )
            return {
                "status": "pending",
                "message": "Insufficient information for verification",
                "source": "none"
            }
        
        return await self.data_provider.verify_seat_availability_unified(
            trip_id=trip_id or 0,  # Use 0 if trip_id not available
            travel_date=travel_date,
            coach_preference=coach_preference,
            train_number=train_number,
            from_station=from_station,
            to_station=to_station,
            quota="GN"
        )
    
    async def _verify_fare(
        self,
        train_number: Optional[str],
        from_station: Optional[str],
        to_station: Optional[str],
        coach_preference: str,
        segment_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Verify fare with fallback."""
        if not train_number or not from_station or not to_station:
            # Fallback to database
            if segment_id:
                return await self.data_provider.verify_fare_unified(
                    segment_id=segment_id,
                    coach_preference=coach_preference
                )
            return {
                "status": "pending",
                "message": "Insufficient information for fare verification",
                "source": "none"
            }
        
        return await self.data_provider.verify_fare_unified(
            segment_id=segment_id or 0,
            coach_preference=coach_preference,
            train_number=train_number,
            from_station=from_station,
            to_station=to_station
        )
