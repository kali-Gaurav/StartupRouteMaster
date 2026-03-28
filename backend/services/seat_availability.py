import logging
from typing import Optional, Dict, Any, List
from datetime import date
import asyncio

# Import the ProviderGateway and its models
from providers.gateway import provider_gateway
# We will use UnifiedAvailability if it's defined, otherwise adapt from gateway's availability data structure.
# For now, let's assume gateway's unlock_route_details provides availability data in a usable list of dicts.
# from backend.providers.models import UnifiedAvailability 

logger = logging.getLogger(__name__)

class SeatAvailabilityService:
    """
    Service responsible for checking seat availability.
    Now delegates all fetching to the ProviderGateway.
    """

    def __init__(self):
        # The service now relies on the ProviderGateway for fetching.
        # Configuration like API keys and enablement status are managed within the gateway.
        logger.info("SeatAvailabilityService initialized. Fetching will be delegated to ProviderGateway.")

    async def get_seat_availability(
        self,
        train_number: str,
        travel_date: str, # Expecting 'YYYY-MM-DD' string
        from_station_code: str,
        to_station_code: str,
        class_code: str,
        quota: str = "GN"
    ) -> Optional[Dict[str, Any]]:
        """
        Delegates seat availability check to the ProviderGateway's unlock_route_details.

        Args:
            train_number: The train number (e.g., "12951").
            travel_date: The date of travel in 'YYYY-MM-DD' format.
            from_station_code: The departure station code (e.g., "NDLS").
            to_station_code: The arrival station code (e.g., "CNB").
            class_code: The class type (e.g., "SL", "3A").
            quota: The quota type (e.g., "GN", "TQ").

        Returns:
            A dictionary containing availability information, matching the original service's structure,
            or None if unavailable or an error occurs.
        """
        logger.debug(f"Delegating seat availability check for train {train_number} on {travel_date} from {from_station_code} to {to_station_code}...")
        
        try:
            # Delegate to the gateway's unlock_route_details, which fetches availability among other things.
            route_details = await provider_gateway.unlock_route_details(
                train_number=train_number,
                source=from_station_code,
                dest=to_station_code,
                date=travel_date
            )
            
            if route_details and route_details.get("success"):
                availability_list_from_gateway = route_details.get("data", {}).get("availability", [])
                
                # The original service returned a specific dictionary structure for availability.
                # We need to adapt the data from the gateway's availability list to match that structure.
                # The gateway's availability is expected to be a list of dicts, e.g.,
                # {'class': '3A', 'available': 5, 'rac': 0, 'waitlist': 12, 'fare': 1500.00, ...}
                
                # Filter and map to the expected output format:
                # { source: "ProviderGateway", success: True, quota: ..., class: ..., data: [...] }
                
                # The original service returned a single dict per class/quota combo.
                # We need to reconstruct that structure if the gateway returns a list.
                # For simplicity, we'll map directly if the data fits.
                # If class_code and quota filtering is needed, it would be applied here.

                if availability_list_from_gateway:
                    # Assuming availability_list_from_gateway contains dicts for different classes/quotas.
                    # The original service returned a dict with 'class', 'quota' etc.
                    # Let's simulate the original return structure:
                    # It seems the original returned one dict per specific availability check,
                    # so if the gateway returns multiple, we might need to pick one or adapt.
                    # For now, let's assume the structure is a list of dictionaries, and we return that list within 'data'.
                    
                    # Adapt to original format: {"source": "ProviderGateway", "success": True, "quota": ..., "class": ..., "data": [...]}
                    # We can use the provided quota and class_code as context, though the gateway might return more specific ones.
                    
                    # The `class` and `quota` keys in the original return might refer to the *specific* ones searched.
                    # We use the input parameters for now.
                    return {
                        "source": "ProviderGateway", # Indicate the unified source
                        "success": True,
                        "quota": quota, 
                        "class": class_code, 
                        "data": availability_list_from_gateway # This is a list of availability dicts
                    }
                else:
                    logger.info(f"No availability data found by gateway for train {train_number} on {travel_date}.")
                    # Return success but empty data if no availability found, matching original pattern.
                    return {"source": "ProviderGateway", "success": True, "quota": quota, "class": class_code, "data": []}

            else:
                error_msg = route_details.get("error", "Unknown error") if route_details else "No route details retrieved"
                logger.warning(f"Seat availability check failed for {train_number} {from_station_code}->{to_station_code} on {travel_date}: {error_msg}")
                return {"source": "ProviderGateway", "success": False, "error": error_msg}
                
        except Exception as exc:
            logger.warning("Seat availability delegation failed for %s %s-%s on %s: %s", train_number, from_station_code, to_station_code, travel_date, exc)
            return {"source": "ProviderGateway", "success": False, "error": str(exc)}

# Example usage (if needed for testing or demonstration)
# async def main():
#     service = SeatAvailabilityService()
#     availability = await service.get_seat_availability(
#         train_no="12951", 
#         date="2026-03-23", 
#         from_station="NDLS", 
#         to_station="CNB", 
#         class_code="3A", 
#         quota="GN"
#     )
#     print(availability)

# if __name__ == "__main__":
#     asyncio.run(main())
