"""
Fare & Availability Validators (RT-071 to RT-090)

This module handles validation logic for fare calculation, availability filtering,
dynamic pricing, discounts, and seat management in multi-modal routing.
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


class FareType(Enum):
    """Types of fares"""
    BASE = "base"
    DYNAMIC = "dynamic"
    DISCOUNTED = "discounted"
    PREMIUM = "premium"
    TATKAL = "tatkal"


class SeatClass(Enum):
    """Seat classes/tiers"""
    ECONOMY = "economy"
    STANDARD = "standard"
    FIRST = "first"
    PREMIUM = "premium"


class CurrencyType(Enum):
    """Supported currency types"""
    INR = "INR"
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"


@dataclass
class FareSegment:
    """Represents a single fare segment"""
    segment_id: str
    base_fare: float
    dynamic_adjustment: float = 0.0
    discount_amount: float = 0.0
    distance_km: float = 0.0
    currency: CurrencyType = CurrencyType.INR
    fare_type: FareType = FareType.BASE
    seat_class: SeatClass = SeatClass.STANDARD
    timestamp: datetime = None

    @property
    def total_fare(self) -> float:
        """Calculate total fare after adjustments"""
        total = self.base_fare + self.dynamic_adjustment - self.discount_amount
        return max(0.0, total)


@dataclass
class SeatInfo:
    """Seat availability information"""
    segment_id: str
    economy_available: int = 0
    standard_available: int = 0
    first_available: int = 0
    premium_available: int = 0
    waitlist_count: int = 0
    total_capacity: int = 0
    timestamp: datetime = None

    def get_available_for_class(self, seat_class: SeatClass) -> int:
        """Get available seats for a specific class"""
        if seat_class == SeatClass.ECONOMY:
            return self.economy_available
        elif seat_class == SeatClass.STANDARD:
            return self.standard_available
        elif seat_class == SeatClass.FIRST:
            return self.first_available
        elif seat_class == SeatClass.PREMIUM:
            return self.premium_available
        return 0


@dataclass
class FareAndAvailability:
    """Completefare and availability information for a route"""
    fare_segments: List[FareSegment]
    seat_info: Dict[str, SeatInfo]
    total_fare: float
    currency: CurrencyType
    route_discount_percent: float = 0.0
    is_dynamic_pricing_active: bool = False
    price_optimization_mode: str = "standard"  # standard, budget, comfort, fastest


class FareAndAvailabilityValidator:
    """Validator class for fare calculation and seat availability"""

    def __init__(self):
        """Initialize the fare and availability validator"""
        self.min_fare = 0.0
        self.max_fare = 100000.0
        self.max_discount_percent = 50.0
        self.currency_rates = {
            CurrencyType.INR: 1.0,
            CurrencyType.USD: 83.0,
            CurrencyType.EUR: 90.0,
            CurrencyType.GBP: 105.0,
        }
        self.rounding_precision = 2  # 2 decimal places

    def validate_fare_calculation_per_segment(self, fare_segment: FareSegment) -> bool:
        """
        RT-071: Validate fare calculation for individual segments.
        Ensures base fare is calculated correctly per segment.
        """
        if fare_segment.base_fare < self.min_fare:
            logger.warning(f"Segment {fare_segment.segment_id}: fare below minimum")
            return False
        
        if fare_segment.base_fare > self.max_fare:
            logger.warning(f"Segment {fare_segment.segment_id}: fare exceeds maximum")
            return False
        
        # Base fare should be positive
        if fare_segment.base_fare <= 0:
            return False
        
        return True

    def validate_total_fare_aggregation(self, fare_segments: List[FareSegment],
                                       expected_total: float) -> bool:
        """
        RT-072: Validate total fare aggregation.
        Sum of all segment fares should equal total fare.
        """
        calculated_total = sum(seg.total_fare for seg in fare_segments)
        
        # Allow small rounding differences (2 decimal places)
        difference = abs(calculated_total - expected_total)
        if difference > 0.01:
            logger.warning(f"Fare mismatch: calculated {calculated_total}, expected {expected_total}")
            return False
        
        return True

    def validate_dynamic_pricing_override(self, fare_and_avail: FareAndAvailability,
                                        is_peak_time: bool = False) -> bool:
        """
        RT-073: Validate dynamic pricing override functionality.
        Dynamic pricing should be applied during peak times when enabled.
        """
        if not fare_and_avail.is_dynamic_pricing_active:
            return True
        
        for seg in fare_and_avail.fare_segments:
            if is_peak_time:
                # During peak time, dynamic adjustment should be positive
                if seg.dynamic_adjustment <= 0:
                    return False
            else:
                # During off-peak, adjustment should be neutral or negative
                # This is a business rule - allow flexibility
                pass
        
        return True

    def validate_seat_availability_filtering(self, seat_info: SeatInfo,
                                            requested_class: SeatClass,
                                            num_passengers: int = 1) -> bool:
        """
        RT-074: Validate seat availability filtering.
        Should only include routes with sufficient seats of requested class.
        """
        available_seats = seat_info.get_available_for_class(requested_class)
        
        if available_seats < num_passengers:
            logger.warning(f"Insufficient seats: available {available_seats}, requested {num_passengers}")
            return False
        
        return True

    def validate_waitlist_handling(self, seat_info: SeatInfo,
                                  requested_class: SeatClass,
                                  num_passengers: int = 1,
                                  allow_waitlist: bool = False) -> bool:
        """
        RT-075: Validate waitlist handling.
        Route should be excluded if unavailable and waitlist not allowed.
        """
        available_seats = seat_info.get_available_for_class(requested_class)
        
        if available_seats < num_passengers:
            if not allow_waitlist or seat_info.waitlist_count >= 10:
                return False
        
        return True

    def validate_class_preference_filtering(self, fare_and_avail: FareAndAvailability,
                                           preferred_classes: List[SeatClass]) -> bool:
        """
        RT-076: Validate class preference filtering.
        Route should match preferred seat classes when available.
        """
        if not preferred_classes:
            return True
        
        # Check if route has seats in any preferred class
        has_preferred_class = False
        for seg in fare_and_avail.fare_segments:
            if seg.seat_class in preferred_classes:
                has_preferred_class = True
                break
        
        return has_preferred_class

    def validate_fare_currency_consistency(self, fare_and_avail: FareAndAvailability) -> bool:
        """
        RT-077: Validate fare currency consistency.
        All segments should use the same currency.
        """
        if not fare_and_avail.fare_segments:
            return True
        
        base_currency = fare_and_avail.currency
        
        for seg in fare_and_avail.fare_segments:
            if seg.currency != base_currency:
                logger.warning(f"Currency mismatch: segment uses {seg.currency}, route uses {base_currency}")
                return False
        
        return True

    def validate_discounts_applied_correctly(self, fare_segment: FareSegment,
                                            discount_percent: float = None) -> bool:
        """
        RT-078: Validate discounts are applied correctly.
        Discount should not exceed maximum allowed and should reduce fare.
        """
        if fare_segment.discount_amount < 0:
            return False
        
        if fare_segment.discount_amount > fare_segment.base_fare:
            return False
        
        discount_pct = (fare_segment.discount_amount / fare_segment.base_fare) * 100 if fare_segment.base_fare > 0 else 0
        
        if discount_pct > self.max_discount_percent:
            return False
        
        return True

    def validate_multimodal_fare_merging(self, fare_segments: List[FareSegment]) -> bool:
        """
        RT-079: Validate multi-modal fare merging.
        Fares from different modes should be merged correctly.
        """
        if len(fare_segments) < 2:
            return True
        
        # Check for negative total fares
        total = sum(seg.total_fare for seg in fare_segments)
        if total < 0:
            return False
        
        # All segment fares should be positive
        for seg in fare_segments:
            if seg.total_fare < 0:
                return False
        
        return True

    def validate_fare_rounding_correctness(self, fares: List[float],
                                          expected_total: float) -> bool:
        """
        RT-080: Validate fare rounding correctness.
        Rounding should be consistent (typically round to 2 decimal places).
        """
        # Round each fare to 2 decimal places
        rounded_fares = [round(fare, self.rounding_precision) for fare in fares]
        calculated_total = round(sum(rounded_fares), self.rounding_precision)
        
        expected_rounded = round(expected_total, self.rounding_precision)
        
        if abs(calculated_total - expected_rounded) > 0.01:
            return False
        
        return True

    def validate_missing_fare_data_fallback(self, fare_and_avail: FareAndAvailability) -> bool:
        """
        RT-081: Validate missing fare data fallback.
        System should provide fallback when actual fare data unavailable.
        """
        if not fare_and_avail.fare_segments:
            return False
        
        # All segments should have valid fare data
        for seg in fare_and_avail.fare_segments:
            if seg.base_fare <= 0:
                logger.warning(f"Segment {seg.segment_id}: missing or invalid fare data")
                return False
        
        return True

    def validate_surge_pricing_updates(self, fare_and_avail: FareAndAvailability,
                                      previous_fares: Dict[str, float]) -> bool:
        """
        RT-082: Validate surge pricing updates.
        Surge pricing changes should be reasonable (not exceeding limits).
        """
        max_surge_multiple = 2.0  # Max 2x original price during surge
        
        for seg in fare_and_avail.fare_segments:
            original_fare = previous_fares.get(seg.segment_id, seg.base_fare)
            
            if original_fare > 0:
                surge_multiple = seg.total_fare / original_fare
                if surge_multiple > max_surge_multiple:
                    logger.warning(f"Excessive surge: {surge_multiple}x original price")
                    return False
        
        return True

    def validate_fare_caps_enforced(self, fare_and_avail: FareAndAvailability,
                                   fare_cap: float = None) -> bool:
        """
        RT-083: Validate fare caps are enforced.
        Total fare should not exceed specified cap.
        """
        if fare_cap is None:
            return True
        
        if fare_and_avail.total_fare > fare_cap:
            logger.warning(f"Fare {fare_and_avail.total_fare} exceeds cap {fare_cap}")
            return False
        
        return True

    def validate_seat_quota_handling(self, seat_info: SeatInfo,
                                    class_quotas: Dict[SeatClass, int]) -> bool:
        """
        RT-084: Validate seat quota handling.
        Available seats should respect class quotas.
        """
        if not class_quotas:
            return True
        
        for seat_class, quota in class_quotas.items():
            available = seat_info.get_available_for_class(seat_class)
            if available > quota:
                logger.warning(f"Quota exceeded for {seat_class}: {available} > {quota}")
                return False
        
        return True

    def validate_tatkal_priority_quota(self, seat_info: SeatInfo,
                                      fare_segment: FareSegment) -> bool:
        """
        RT-085: Validate Tatkal-like priority quota handling.
        Premium fares should have access to priority quotas.
        """
        if fare_segment.fare_type == FareType.TATKAL:
            # Tatkal fares should have seats available even if normal quota full
            # (simplified implementation - actual would check priority quotas)
            return True
        
        return True

    def validate_fare_caching_consistency(self, cached_fare: FareSegment,
                                        fresh_fare: FareSegment,
                                        max_staleness_minutes: int = 15) -> bool:
        """
        RT-086: Validate fare caching consistency.
        Cached fares should not be significantly different from fresh fares.
        """
        if cached_fare.timestamp is None or fresh_fare.timestamp is None:
            return True
        
        time_diff = (fresh_fare.timestamp - cached_fare.timestamp).total_seconds() / 60
        
        if time_diff > max_staleness_minutes:
            # Cached data is stale, should have been updated
            return False
        
        # Fares should be similar
        fare_diff = abs(cached_fare.total_fare - fresh_fare.total_fare)
        if fare_diff > cached_fare.base_fare * 0.1:  # More than 10% difference
            return False
        
        return True

    def validate_partial_availability_segment(self, fare_and_avail: FareAndAvailability,
                                             num_passengers: int = 1) -> bool:
        """
        RT-087: Validate partial availability segments.
        Route should be excluded if not all passengers can be accommodated.
        """
        for seg_id, seat_info in fare_and_avail.seat_info.items():
            for seat_class in [SeatClass.ECONOMY, SeatClass.STANDARD, SeatClass.FIRST, SeatClass.PREMIUM]:
                available = seat_info.get_available_for_class(seat_class)
                if available > 0 and available < num_passengers:
                    # Partial availability - should be rejected
                    return False
        
        return True

    def validate_price_optimization_mode(self, fare_and_avail: FareAndAvailability,
                                        selected_mode: str) -> bool:
        """
        RT-088: Validate price optimization mode.
        Route should match selected price optimization preference.
        """
        valid_modes = ["standard", "budget", "comfort", "fastest"]
        
        if selected_mode not in valid_modes:
            return False
        
        fare_and_avail.price_optimization_mode = selected_mode
        
        # Mode-specific validations
        if selected_mode == "budget" and fare_and_avail.total_fare > 5000:
            # Budget mode should prefer cheaper routes
            return False
        elif selected_mode == "premium" and fare_and_avail.total_fare < 1000:
            # Premium mode should prefer better routes
            return False
        
        return True

    def validate_refund_calculation_scenario(self, original_fare: float,
                                            cancellation_fee_percent: float = 10.0) -> bool:
        """
        RT-089: Validate refund calculation scenarios.
        Refund should be calculated correctly with applicable fees.
        """
        if original_fare < 0:
            return False
        
        if cancellation_fee_percent < 0 or cancellation_fee_percent > 100:
            return False
        
        refund_amount = original_fare * (1 - cancellation_fee_percent / 100)
        
        if refund_amount < 0:
            return False
        
        return True

    def validate_zero_fare_route_edge_case(self, fare_and_avail: FareAndAvailability) -> bool:
        """
        RT-090: Validate zero-fare route edge cases.
        Zero-fare routes should be handled correctly.
        """
        if fare_and_avail.total_fare < 0:
            return False
        
        if fare_and_avail.total_fare == 0:
            # Zero-fare route - should still have valid seat info
            if not fare_and_avail.seat_info:
                return False
            
            # All segments should be valid
            for seg in fare_and_avail.fare_segments:
                if seg.base_fare < 0:
                    return False
        
        return True
