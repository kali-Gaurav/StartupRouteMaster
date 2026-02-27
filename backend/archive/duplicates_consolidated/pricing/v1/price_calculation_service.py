# backend/services/price_calculation_service.py
import logging
from typing import Dict, Any
from models import Route



logger = logging.getLogger(__name__)

class PriceCalculationService:
    """
    Service to centralize price calculation, applying taxes, fees, and potential surges.
    """
    TAX_RATE = 0.05  # 5% tax
    CONVENIENCE_FEE = 10.00  # Fixed convenience fee of 10.00 INR

    def calculate_final_price(self, route: Route, user_type: str = "standard") -> float:
        """
        Calculate the final price for a given route, applying various charges.

        Args:
            route: The Route object containing base cost.
            user_type: Type of user (e.g., "standard", "premium") for potential future discounts/surges.

        Returns:
            The final calculated price.
        """
        base_cost = route.total_cost
        
        # Apply tax
        cost_after_tax = base_cost * (1 + self.TAX_RATE)
        
        # Apply convenience fee
        final_price = cost_after_tax + self.CONVENIENCE_FEE
        
        # Round to 2 decimal places for currency
        final_price = round(final_price, 2)

        logger.info(f"Calculated price for route {route.id}: Base {base_cost}, Tax {self.TAX_RATE*100}%, Fee {self.CONVENIENCE_FEE} -> Final {final_price}")
        
        return final_price

    def get_price_breakdown(self, route: Route, user_type: str = "standard") -> Dict[str, float]:
        """
        Provides a detailed breakdown of the price calculation.
        """
        base_cost = route.total_cost
        tax_amount = round(base_cost * self.TAX_RATE, 2)
        cost_after_tax = base_cost + tax_amount
        
        final_price = round(cost_after_tax + self.CONVENIENCE_FEE, 2)

        return {
            "base_cost": round(base_cost, 2),
            "tax_rate": self.TAX_RATE,
            "tax_amount": tax_amount,
            "convenience_fee": self.CONVENIENCE_FEE,
            "final_price": final_price,
        }
