# Ensure necessary imports are present (e.g., math for isclose)
import math
from services.vault_service import pnr_vault
from providers.gateway import provider_gateway

class BookingVerificationService:
    """
    Service to verify booking details against real-time data.
    
    With resilience patterns: circuit breaker, retry, and metrics tracking.
    """

    def __init__(self):
        # The service depends on the ProviderGateway for all data fetching.
        # No direct client initialization here; delegation happens in methods.
        logger.info("BookingVerificationService initialized. Will delegate to ProviderGateway.")
        
        # Circuit breakers for different verification types
        self._availability_breaker = circuit_breaker_manager.get_or_create(
            "booking_verification_availability",
            CircuitConfig(failure_threshold=5, timeout_seconds=30.0)
        )
        self._pnr_breaker = circuit_breaker_manager.get_or_create(
            "booking_verification_pnr",
            CircuitConfig(failure_threshold=5, timeout_seconds=30.0)
        )
        self._live_status_breaker = circuit_breaker_manager.get_or_create(
            "booking_verification_live_status",
            CircuitConfig(failure_threshold=5, timeout_seconds=30.0)
        )
        self._fare_breaker = circuit_breaker_manager.get_or_create(
            "booking_verification_fare",
            CircuitConfig(failure_threshold=5, timeout_seconds=30.0)
        )
        
        # Retry policies
        self._availability_retry = RetryPolicy(
            max_attempts=3,
            initial_delay=0.5,
            max_delay=5.0,
            conditions=[
                lambda e: "timeout" in str(e).lower(),
                lambda e: "connection" in str(e).lower()
            ]
        )
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()


    async def verify_availability(self, 
                                 train_number: str, 
                                 from_stn: str, 
                                 to_stn: str, 
                                 travel_date: str, 
                                 class_code: str,
                                 quota: str = "GN") -> Dict[str, Any]:
        """
        [Task 4.9] Real-time availability check for Flex-Booking.
        Checks if seats are actually available for the given class/quota.
        
        Protected by circuit breaker and retry logic.
        """
        logger.info(f"🛰️ [VERIFICATION] Checking availability for {train_number} | {class_code} | {travel_date}")
        
        async def _fetch_availability():
            return await provider_gateway.get_seat_availability(
                train_number=train_number,
                travel_date=travel_date,
                from_stn=from_stn,
                to_stn=to_stn,
                cls=class_code,
                quota=quota
            )
        
        try:
            # Execute with circuit breaker and retry
            availability_list = await self._availability_breaker.execute(
                self._availability_retry.execute,
                _fetch_availability
            )
            
            if not availability_list:
                return {"is_available": False, "reason": "PROVIDER_FAILURE", "message": "Could not fetch live seat data."}
            
            # Find the first valid availability day (usually the specific date requested)
            for day in availability_list:
                # Basic check: availability can be "AVAILABLE", "RLWL", "WL", "NOT AVAILABLE"
                status = day.get("status", "").upper()
                if "AVAILABLE" in status:
                    return {
                        "is_available": True, 
                        "status": status,
                        "count": day.get("current_status_count", 0),
                        "message": "Seats confirmed."
                    }
                elif "WL" in status or "RLWL" in status:
                    # In our system, Waiting List might still be "bookable" but we trigger Flex for confirmed-only users
                    return {
                        "is_available": True, # Still bookable, but maybe warned
                        "status": status,
                        "is_wl": True,
                        "message": f"Waiting list detected: {status}"
                    }
                elif "NOT AVAILABLE" in status:
                    return {"is_available": False, "reason": "SOLD_OUT", "message": "No seats available."}
            
            return {"is_available": False, "reason": "UNKNOWN_AVAILABILITY", "message": "Availability status unclear."}

        except Exception as e:
            logger.error(f"Availability check failed: {e}")
            return {"is_available": False, "reason": "ERROR", "message": str(e)}

    async def verify_booking_details(self, 
                                     pnr_number: Optional[str] = None,
                                     train_number: Optional[str] = None,
                                     travel_date: Optional[str] = None,
                                     from_station_code: Optional[str] = None,
                                     to_station_code: Optional[str] = None,
                                     class_code: Optional[str] = None,
                                     quota: Optional[str] = None,
                                     booking_fare: Optional[float] = None) -> Dict[str, Any]:
        """
        Verifies booking details against live data from providers.

        This is a high-level method that can orchestrate multiple checks.
        It uses PNR, live status, fare, and availability data.
        """
        verification_results = {
            "pnr_status": None,
            "live_status": None,
            "fare_details": None,
            "overall_verification": "Unknown",
            "issues": []
        }

        # --- 1. Verify PNR Status via JIT Vault ---
        if pnr_number:
            blind_index = pnr_vault.get_blind_index(pnr_number)
            logger.info(f"🔒 [VAULT] JIT PNR Verification initiated | Index: {blind_index[:8]}...")
            
            pnr_data = await provider_gateway.get_pnr_status(pnr_number=pnr_number)
            verification_results["pnr_status"] = pnr_data
            if pnr_data and pnr_data.get("success"):
                # Basic check: Does PNR data match basic booking info if available?
                if train_number and pnr_data.get("train_number") != train_number:
                    verification_results["issues"].append("PNR train number mismatch.")
                    logger.warning(f"PNR {pnr_number}: Train number mismatch. PNR shows {pnr_data.get('train_number')}, booking detail has {train_number}.")
                if travel_date and pnr_data.get("travel_date") != travel_date:
                    verification_results["issues"].append("PNR travel date mismatch.")
                    logger.info(f"PNR {pnr_number}: Travel date mismatch. PNR shows {pnr_data.get('travel_date')}, booking detail has {travel_date}.")
                # Add more checks as needed (e.g., stations, class)
            elif pnr_data and not pnr_data.get("success"):
                verification_results["issues"].append(f"PNR verification failed: {pnr_data.get('error')}")
            elif not pnr_data:
                verification_results["issues"].append("PNR lookup failed.")
        
        # --- 2. Verify Live Train Status & ML Predictions ---
        if train_number and travel_date:
            logger.debug(f"Verifying status and predictions for train {train_number} on {travel_date}")
            
            # 2.1 Real-time Status
            live_status_data = await provider_gateway.get_live_status(train_number=train_number, train_date=travel_date)
            verification_results["live_status"] = live_status_data
            
            real_time_delay = 0
            if live_status_data:
                real_time_delay = live_status_data.delay_minutes
                if live_status_data.running_status == "Cancelled":
                    verification_results["issues"].append("Train is cancelled. Preparing recovery routes...")
                    logger.warning(f"Booking Verification: Train {train_number} is cancelled.")
                elif real_time_delay > 120:
                    verification_results["issues"].append(f"Train {train_number} is significantly delayed ({real_time_delay} mins).")

            # 2.2 ML-Based Prediction [Task 103]
            from services.delay_predictor import delay_predictor
            # Parse travel_date for features
            try:
                dt_obj = datetime.strptime(travel_date, "%Y-%m-%d")
                prediction = await delay_predictor.predict_delay(
                    train_id=int(train_number),
                    day_of_week=dt_obj.weekday(),
                    month=dt_obj.month,
                    departure_hour=12 # Fallback if not provided
                )
                
                if prediction > 120 and real_time_delay <= 120:
                    verification_results["issues"].append(f"⚠️ PREDICTIVE ALERT: High probability of >2hr delay ({int(prediction)} mins predicted).")
                    logger.warning(f"ML Predictor flagged potential disruption for train {train_number}: {prediction} mins")
            except Exception as e:
                logger.error(f"Failed to fetch ML Prediction: {e}")

            if not live_status_data and not prediction:
                 verification_results["issues"].append("Live train status and prediction lookup failed.")


        # --- 3. Verify Fare Consistency ---
        # This check requires booking_fare, class_code, quota, stations, train_number, travel_date
        if booking_fare is not None and class_code and quota and from_station_code and to_station_code and train_number and travel_date:
            logger.debug(f"Verifying fare for train {train_number} ({from_station_code}->{to_station_code}) on {travel_date}")
            fare_list = await provider_gateway.get_fare(
                train_number=train_number, travel_date=travel_date,
                from_station_code=from_station_code, to_station_code=to_station_code,
                class_code=class_code, quota=quota
            )
            verification_results["fare_details"] = fare_list

            if fare_list:
                # Find the matching fare if available
                matching_fare = next((item for item in fare_list if item.get('class_code') == class_code and item.get('quota') == quota), None)
                
                if matching_fare and matching_fare.get('fare') is not None:
                    # Compare booking fare with fetched fare. Allow for small tolerance.
                    fetched_fare = matching_fare.get('fare')
                    if not math.isclose(booking_fare, fetched_fare, rel_tol=0.05): # Allow 5% tolerance
                        verification_results["issues"].append(f"Fare mismatch: Booking fare ${booking_fare} vs fetched fare ${fetched_fare}.")
                        logger.warning(f"Booking Verification: Fare mismatch for {train_number} ({class_code}/{quota}). Booking: ${booking_fare}, Fetched: ${fetched_fare}")
                else:
                    logger.info(f"Fare details not found for class {class_code}, quota {quota} for train {train_number} on {travel_date}.")
            else:
                verification_results["issues"].append("Fare lookup failed.")
        
        # --- Determine Overall Verification Status ---
        if not verification_results["issues"]:
            verification_results["overall_verification"] = "Success"
        elif len(verification_results["issues"]) > 0 and len(verification_results["issues"]) < 3:
            verification_results["overall_verification"] = "Warning"
        else:
            verification_results["overall_verification"] = "Failed"
        
        # Record metrics
        await self._record_metrics(verification_results)
            
        return verification_results

    # =========================================================================
    # RESILIENCE PATTERNS
    # =========================================================================

    async def _record_metrics(self, result: Dict[str, Any]):
        """Record verification metrics for monitoring."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "overall_status": result.get("overall_verification", "Unknown"),
                "issues_count": len(result.get("issues", [])),
                "has_pnr_check": result.get("pnr_status") is not None,
                "has_live_status": result.get("live_status") is not None,
                "has_fare_check": result.get("fare_details") is not None
            })

    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_verifications": 0, "success_rate": 0.0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["overall_status"] == "Success")
        with_issues = sum(1 for m in self._metrics if m["issues_count"] > 0)
        
        return {
            "total_verifications": total,
            "successful_verifications": successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "verifications_with_issues": with_issues,
            "circuit_breaker_states": {
                "availability": self._availability_breaker.get_state().value,
                "pnr": self._pnr_breaker.get_state().value,
                "live_status": self._live_status_breaker.get_state().value,
                "fare": self._fare_breaker.get_state().value
            }
        }

    def health_check(self) -> dict:
        """Check service health."""
        return {
            "status": "healthy",
            "circuit_breakers": {
                "availability": self._availability_breaker.get_state().value,
                "pnr": self._pnr_breaker.get_state().value,
                "live_status": self._live_status_breaker.get_state().value,
                "fare": self._fare_breaker.get_state().value
            },
            "metrics": self.get_metrics()
        }

    def reset_circuit_breakers(self):
        """Reset all circuit breakers."""
        self._availability_breaker.reset()
        self._pnr_breaker.reset()
        self._live_status_breaker.reset()
        self._fare_breaker.reset()
        logger.info("All circuit breakers reset for booking verification service")


booking_verification_service = BookingVerificationService()
