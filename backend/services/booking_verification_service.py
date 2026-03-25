"""
Service for real-time booking verification and alerts.

This service utilizes the ProviderGateway to fetch live train status,
fare information, and PNR status to provide real-time verification
and potential alerts related to bookings.
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

# Import Gateway and necessary models
from providers.gateway import provider_gateway
from providers.models import UnifiedLiveStatus, UnifiedPNRStatus

logger = logging.getLogger(__name__)

class BookingVerificationService:
    """
    Service to verify booking details against real-time data.
    """

    def __init__(self):
        # The service depends on the ProviderGateway for all data fetching.
        # No direct client initialization here; delegation happens in methods.
        logger.info("BookingVerificationService initialized. Will delegate to ProviderGateway.")

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

        # --- 1. Verify PNR Status ---
        if pnr_number:
            logger.debug(f"Verifying PNR: {pnr_number}")
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
        
        # --- 2. Verify Live Train Status ---
        if train_number and travel_date:
            logger.debug(f"Verifying live status for train {train_number} on {travel_date}")
            live_status_data = await provider_gateway.get_live_status(train_number=train_number, train_date=travel_date)
            verification_results["live_status"] = live_status_data
            if live_status_data:
                # Check for significant delays or cancellations
                if live_status_data.running_status == "Cancelled":
                    verification_results["issues"].append("Train is cancelled.")
                    logger.warning(f"Booking Verification: Train {train_number} is cancelled.")
                elif live_status_data.delay_minutes > 120: # Example threshold for significant delay
                    verification_results["issues"].append(f"Train {train_number} is significantly delayed ({live_status_data.delay_minutes} mins).")
                    logger.warning(f"Booking Verification: Train {train_number} is significantly delayed.")
            elif not live_status_data:
                 verification_results["issues"].append("Live train status lookup failed.")


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
            
        return verification_results

# Ensure necessary imports are present (e.g., math for isclose)
import math

booking_verification_service = BookingVerificationService()
