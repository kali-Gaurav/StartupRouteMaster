# backend/services/price_calculation_service.py
import logging
from typing import Dict, Any




logger = logging.getLogger(__name__)

class PriceCalculationService:
    """
    Service to centralize price calculation, applying taxes, fees, and potential surges.
    """
    TAX_RATE = 0.05  # 5% tax
    CONVENIENCE_FEE = 10.00  # Fixed convenience fee of 10.00 INR
    SEAT_LOCK_FEE = 25.00  # Fee for holding seat inventory
    PLATFORM_COMMISSION_RATE = 0.02 # 2% platform commission

    def _get_base_cost(self, route: Any) -> float:
        if hasattr(route, "total_cost"):
            try:
                return float(getattr(route, "total_cost") or 0.0)
            except (TypeError, ValueError):
                pass

        if hasattr(route, "route_data") and isinstance(getattr(route, "route_data"), dict):
            return float(route.route_data.get("total_cost", route.route_data.get("total_fare", 0.0)) or 0.0)

        if isinstance(route, dict):
            return float(route.get("total_cost", route.get("total_fare", 0.0)) or 0.0)

        return 0.0

    def calculate_final_price(self, route: Any, user_type: str = "standard") -> float:
        """
        Calculate the final price for a given route, applying various charges.

        Args:
            route: The Route object containing base cost.
            user_type: Type of user (e.g., "standard", "premium") for potential future discounts/surges.

        Returns:
            The final calculated price.
        """
        base_cost = self._get_base_cost(route)
        
        # Apply tax
        tax_amount = base_cost * self.TAX_RATE
        
        # Apply platform commission
        commission = base_cost * self.PLATFORM_COMMISSION_RATE
        
        # Apply convenience fee and seat lock fee
        final_price = base_cost + tax_amount + commission + self.CONVENIENCE_FEE + self.SEAT_LOCK_FEE
        
        # Round to 2 decimal places for currency
        final_price = round(final_price, 2)

        route_id = getattr(route, "id", getattr(route, "route_id", None))
        logger.info(
            f"Calculated price for route {route_id}: Base {base_cost}, Tax {self.TAX_RATE*100}%, Fee {self.CONVENIENCE_FEE} -> Final {final_price}"
        )
        
        return final_price

    def get_price_breakdown(self, route: Any, user_type: str = "standard") -> Dict[str, float]:
        """
        Provides a detailed breakdown of the price calculation.
        """
        base_cost = self._get_base_cost(route)
        tax_amount = round(base_cost * self.TAX_RATE, 2)
        commission = round(base_cost * self.PLATFORM_COMMISSION_RATE, 2)
        
        final_price = round(base_cost + tax_amount + commission + self.CONVENIENCE_FEE + self.SEAT_LOCK_FEE, 2)
 
        return {
            "base_cost": round(base_cost, 2),
            "tax_rate": self.TAX_RATE,
            "tax_amount": tax_amount,
            "platform_commission": commission,
            "convenience_fee": self.CONVENIENCE_FEE,
            "seat_lock_fee": self.SEAT_LOCK_FEE,
            "final_price": final_price,
        }
