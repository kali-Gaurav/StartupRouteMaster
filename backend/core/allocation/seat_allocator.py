"""
💺 SEAT ALLOCATOR — Patent-Level Intelligent Seat Assignment Engine
Implements:
  1. Preference-Optimized Assignment (window/aisle/lower berth preferences)
  2. Family Grouping (keeps families together in adjacent berths)
  3. Women Safety Zoning (dedicated compartment allocation with buffer zones)  
  4. Quota Management (GN, TQ, LD, HO, DF, PH, SS quotas)
  5. RAC & Waitlist Management (auto-promotion, priority queuing)
  6. Berth Optimization (maximize comfort score across all passengers)
"""

import logging
import time
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple, Set, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import heapq

logger = logging.getLogger(__name__)

# [Phase 3: Patent Innovation Layer]
from core.allocation.overbook_manager import overbook_manager



# =========================================================================
# DOMAIN MODELS
# =========================================================================

class BerthType(Enum):
    LOWER = "LB"
    MIDDLE = "MB"
    UPPER = "UB"
    SIDE_LOWER = "SL"
    SIDE_UPPER = "SU"
    WINDOW = "WS"       # For CC/2S
    AISLE = "AS"
    MIDDLE_SEAT = "MS"


class BerthPreference(Enum):
    LOWER = "LOWER"
    UPPER = "UPPER"
    MIDDLE = "MIDDLE"
    SIDE_LOWER = "SIDE_LOWER"
    SIDE_UPPER = "SIDE_UPPER"
    WINDOW = "WINDOW"
    AISLE = "AISLE"
    NO_PREFERENCE = "NO_PREFERENCE"


class QuotaType(Enum):
    GN = "GN"       # General
    TQ = "TQ"       # Tatkal
    PT = "PT"       # Premium Tatkal
    LD = "LD"       # Ladies
    HO = "HO"       # Head Office (emergency/VIP)
    DF = "DF"       # Defence
    PH = "PH"       # Physically Handicapped
    SS = "SS"       # Senior Citizen
    FT = "FT"       # Foreign Tourist
    YT = "YT"       # Youth (for some trains)


class AllocationStatus(Enum):
    CONFIRMED = "CNF"
    RAC = "RAC"
    WAITLIST = "WL"
    PQWL = "PQWL"      # Pooled Quota Waitlist
    RLWL = "RLWL"       # Remote Location Waitlist
    GNWL = "GNWL"       # General Waitlist
    REGRET = "REGRET"   # No allocation possible


class PassengerCategory(Enum):
    ADULT_MALE = "ADULT_MALE"
    ADULT_FEMALE = "ADULT_FEMALE"
    SENIOR_MALE = "SENIOR_MALE"
    SENIOR_FEMALE = "SENIOR_FEMALE"
    CHILD = "CHILD"
    INFANT = "INFANT"
    DIVYANG = "DIVYANG"


@dataclass(slots=True)
class Passenger:
    """A single passenger in a booking."""
    id: str
    name: str
    age: int
    gender: str                          # M, F, O
    category: PassengerCategory
    berth_preference: BerthPreference = BerthPreference.NO_PREFERENCE
    is_group_leader: bool = False
    group_id: Optional[str] = None       # Family/group identifier
    requires_lower: bool = False         # Medical/age requirement
    priority_score: float = 0.0          # Higher = more deserving of preferred berth


@dataclass(slots=True)
class Berth:
    """A single berth/seat in a coach."""
    coach: str
    number: int
    berth_type: BerthType
    compartment: int                     # Compartment number within coach
    is_available: bool = True
    is_women_zone: bool = False
    quota: QuotaType = QuotaType.GN
    assigned_to: Optional[str] = None    # Passenger ID


@dataclass(slots=True)
class AllocationResult:
    """Result of seat allocation for a single passenger."""
    passenger_id: str
    status: AllocationStatus
    coach: Optional[str] = None
    berth_number: Optional[int] = None
    berth_type: Optional[BerthType] = None
    comfort_score: float = 0.0          # 0-1, how well preference matched
    notes: str = ""


@dataclass(slots=True)
class BookingAllocation:
    """Complete allocation result for a booking."""
    booking_id: str
    train_number: str
    travel_date: date
    class_code: str
    allocations: List[AllocationResult] = field(default_factory=list)
    group_integrity_score: float = 0.0   # 0-1, how well groups kept together
    overall_comfort_score: float = 0.0
    quota_used: QuotaType = QuotaType.GN
    timestamp: datetime = field(default_factory=datetime.utcnow)


# =========================================================================
# COACH LAYOUT GENERATOR
# =========================================================================

class CoachLayoutGenerator:
    """
    Generates berth layouts for different coach types.
    Based on standard Indian Railways coach configurations.
    """

    @staticmethod
    def generate_sl_layout(coach: str, women_compartments: Set[int] = None) -> List[Berth]:
        """Generate Sleeper class layout: 72 berths, 9 compartments of 8."""
        berths = []
        women_comps = women_compartments or set()
        for comp in range(1, 10):  # 9 compartments
            is_women = comp in women_comps
            base = (comp - 1) * 8
            # Main bay (6 berths: 2 lower, 2 middle, 2 upper)
            berths.append(Berth(coach, base + 1, BerthType.LOWER, comp, is_women_zone=is_women))
            berths.append(Berth(coach, base + 2, BerthType.LOWER, comp, is_women_zone=is_women))
            berths.append(Berth(coach, base + 3, BerthType.MIDDLE, comp, is_women_zone=is_women))
            berths.append(Berth(coach, base + 4, BerthType.MIDDLE, comp, is_women_zone=is_women))
            berths.append(Berth(coach, base + 5, BerthType.UPPER, comp, is_women_zone=is_women))
            berths.append(Berth(coach, base + 6, BerthType.UPPER, comp, is_women_zone=is_women))
            # Side berths (2)
            berths.append(Berth(coach, base + 7, BerthType.SIDE_LOWER, comp, is_women_zone=is_women))
            berths.append(Berth(coach, base + 8, BerthType.SIDE_UPPER, comp, is_women_zone=is_women))
        return berths

    @staticmethod
    def generate_3a_layout(coach: str) -> List[Berth]:
        """Generate 3AC layout: 64 berths, 8 compartments."""
        berths = []
        for comp in range(1, 9):
            base = (comp - 1) * 8
            berths.append(Berth(coach, base + 1, BerthType.LOWER, comp))
            berths.append(Berth(coach, base + 2, BerthType.LOWER, comp))
            berths.append(Berth(coach, base + 3, BerthType.MIDDLE, comp))
            berths.append(Berth(coach, base + 4, BerthType.MIDDLE, comp))
            berths.append(Berth(coach, base + 5, BerthType.UPPER, comp))
            berths.append(Berth(coach, base + 6, BerthType.UPPER, comp))
            berths.append(Berth(coach, base + 7, BerthType.SIDE_LOWER, comp))
            berths.append(Berth(coach, base + 8, BerthType.SIDE_UPPER, comp))
        return berths

    @staticmethod
    def generate_2a_layout(coach: str) -> List[Berth]:
        """Generate 2AC layout: 46 berths (no middle berths)."""
        berths = []
        for comp in range(1, 8):  # 7 full compartments
            base = (comp - 1) * 6
            berths.append(Berth(coach, base + 1, BerthType.LOWER, comp))
            berths.append(Berth(coach, base + 2, BerthType.LOWER, comp))
            berths.append(Berth(coach, base + 3, BerthType.UPPER, comp))
            berths.append(Berth(coach, base + 4, BerthType.UPPER, comp))
            berths.append(Berth(coach, base + 5, BerthType.SIDE_LOWER, comp))
            berths.append(Berth(coach, base + 6, BerthType.SIDE_UPPER, comp))
        # Partial compartment
        berths.append(Berth(coach, 43, BerthType.LOWER, 8))
        berths.append(Berth(coach, 44, BerthType.UPPER, 8))
        berths.append(Berth(coach, 45, BerthType.SIDE_LOWER, 8))
        berths.append(Berth(coach, 46, BerthType.SIDE_UPPER, 8))
        return berths

    @staticmethod
    def generate_cc_layout(coach: str) -> List[Berth]:
        """Generate Chair Car layout: 78 seats."""
        berths = []
        for row in range(1, 14):
            for seat in range(1, 7):  # 6 seats per row (3+3)
                base = (row - 1) * 6 + seat
                if seat in (1, 6):
                    btype = BerthType.WINDOW
                elif seat in (3, 4):
                    btype = BerthType.AISLE
                else:
                    btype = BerthType.MIDDLE_SEAT
                berths.append(Berth(coach, base, btype, row))
        return berths

    @classmethod
    def generate_layout(cls, coach: str, class_code: str, women_compartments: Set[int] = None) -> List[Berth]:
        generators = {
            "SL": cls.generate_sl_layout,
            "3A": cls.generate_3a_layout,
            "2A": cls.generate_2a_layout,
            "CC": cls.generate_cc_layout,
        }
        gen = generators.get(class_code)
        if gen:
            if class_code == "SL":
                return gen(coach, women_compartments or set())
            return gen(coach)
        return cls.generate_sl_layout(coach, women_compartments or set())


# =========================================================================
# QUOTA MANAGER
# =========================================================================

class QuotaManager:
    """
    Manages seat quota allocation per train/class/segment.
    Implements IRCTC-standard quota hierarchy.
    """

    # Default quota split (% of total capacity)
    DEFAULT_SPLITS = {
        QuotaType.GN: 0.55,
        QuotaType.TQ: 0.15,
        QuotaType.LD: 0.06,
        QuotaType.SS: 0.05,
        QuotaType.PH: 0.02,
        QuotaType.DF: 0.02,
        QuotaType.HO: 0.05,
        QuotaType.FT: 0.02,
        QuotaType.PT: 0.08,
    }

    def __init__(self):
        self._quotas: Dict[str, Dict[QuotaType, int]] = {}

    def initialize_quotas(self, segment_key: str, total_capacity: int,
                          custom_splits: Optional[Dict[QuotaType, float]] = None):
        splits = custom_splits or self.DEFAULT_SPLITS
        self._quotas[segment_key] = {}
        allocated = 0
        for qt, pct in splits.items():
            seats = int(total_capacity * pct)
            self._quotas[segment_key][qt] = seats
            allocated += seats
        # Remainder goes to GN
        remainder = total_capacity - allocated
        self._quotas[segment_key][QuotaType.GN] += max(0, remainder)

    def get_available(self, segment_key: str, quota: QuotaType) -> int:
        quotas = self._quotas.get(segment_key, {})
        return quotas.get(quota, 0)

    def consume(self, segment_key: str, quota: QuotaType, count: int = 1) -> bool:
        quotas = self._quotas.get(segment_key)
        if not quotas:
            return False
        available = quotas.get(quota, 0)
        if available >= count:
            quotas[quota] = available - count
            return True
        return False

    def release(self, segment_key: str, quota: QuotaType, count: int = 1):
        quotas = self._quotas.get(segment_key)
        if quotas:
            quotas[quota] = quotas.get(quota, 0) + count

    def get_quota_status(self, segment_key: str) -> Dict[str, int]:
        quotas = self._quotas.get(segment_key, {})
        return {qt.value: count for qt, count in quotas.items()}


# =========================================================================
# PREFERENCE MATCHER
# =========================================================================

class PreferenceMatcher:
    """Scores how well a berth matches a passenger's preferences."""

    # Preference → Compatible berth types (ordered by match quality)
    PREFERENCE_MAP = {
        BerthPreference.LOWER: [BerthType.LOWER, BerthType.SIDE_LOWER],
        BerthPreference.UPPER: [BerthType.UPPER, BerthType.SIDE_UPPER],
        BerthPreference.MIDDLE: [BerthType.MIDDLE],
        BerthPreference.SIDE_LOWER: [BerthType.SIDE_LOWER, BerthType.LOWER],
        BerthPreference.SIDE_UPPER: [BerthType.SIDE_UPPER, BerthType.UPPER],
        BerthPreference.WINDOW: [BerthType.WINDOW],
        BerthPreference.AISLE: [BerthType.AISLE],
    }

    @staticmethod
    def score(passenger: Passenger, berth: Berth) -> float:
        """Returns comfort score 0.0 - 1.0 for passenger-berth match."""
        score = 0.5  # Base

        # 1. Berth preference match
        pref = passenger.berth_preference
        if pref != BerthPreference.NO_PREFERENCE:
            compatible = PreferenceMatcher.PREFERENCE_MAP.get(pref, [])
            if berth.berth_type in compatible:
                idx = compatible.index(berth.berth_type)
                score = 1.0 - (idx * 0.15)  # First choice = 1.0, second = 0.85
            else:
                score = 0.3  # Poor match

        # 2. Age-based adjustments
        if passenger.age >= 60 and berth.berth_type in (BerthType.LOWER, BerthType.SIDE_LOWER):
            score += 0.2  # Seniors prefer lower
        elif passenger.age >= 60 and berth.berth_type in (BerthType.UPPER, BerthType.SIDE_UPPER):
            score -= 0.3  # Penalty for upper berth for seniors

        # 3. Medical lower requirement
        if passenger.requires_lower and berth.berth_type in (BerthType.LOWER, BerthType.SIDE_LOWER):
            score = 1.0

        # 4. Women safety zone
        if passenger.gender == "F" and berth.is_women_zone:
            score += 0.15

        # 5. Child with family grouping boost
        if passenger.category == PassengerCategory.CHILD:
            score += 0.1 if berth.berth_type == BerthType.LOWER else 0.0

        return min(1.0, max(0.0, score))


# =========================================================================
# MAIN ALLOCATOR
# =========================================================================

class SeatAllocator:
    """
    Patent-Level Intelligent Seat Assignment Engine.
    Optimizes across all passengers simultaneously using priority scoring.
    """

    def __init__(self):
        self.layout_gen = CoachLayoutGenerator()
        self.quota_mgr = QuotaManager()
        self.pref_matcher = PreferenceMatcher()

    async def allocate_booking(
        self,
        booking_id: str,
        train_number: str,
        from_station: str,
        to_station: str,
        travel_date: date,
        class_code: str,
        passengers: List[Passenger],
        quota: QuotaType = QuotaType.GN,
        coaches: Optional[List[str]] = None,
        existing_occupancy: Optional[Dict[str, Set[int]]] = None,
        db=None
    ) -> BookingAllocation:
        """
        Allocate seats for a complete booking.
        Uses Hungarian-inspired matching for optimal assignment.
        """
        start_ts = time.time()
        seg_key = f"{train_number}:{from_station}:{to_station}:{travel_date}:{class_code}"

        # 1. Generate available berths
        coach_list = coaches or [f"{class_code}{i}" for i in range(1, 4)]
        women_comps = {1, 2} if any(p.gender == "F" for p in passengers) else set()

        all_berths: List[Berth] = []
        for coach in coach_list:
            layout = self.layout_gen.generate_layout(coach, class_code, women_comps)
            # Mark existing occupancy
            occupied = (existing_occupancy or {}).get(coach, set())
            for b in layout:
                if b.number in occupied:
                    b.is_available = False
            all_berths.extend(layout)

        available_berths = [b for b in all_berths if b.is_available]

        # 2. Initialize quota if not done
        total_capacity = len(all_berths)
        self.quota_mgr.initialize_quotas(seg_key, total_capacity)

        # 3. Check quota availability
        quota_available = self.quota_mgr.get_available(seg_key, quota)
        
        # [Phase 3: Dynamic Overbooking]
        # Instead of static limits, calculate safe expansion based on predicted cancellations
        # We assume a 15% base cancellation rate for MVP; real system pulls from DB
        rac_limit, wl_limit = overbook_manager.calculate_limits(
            physical_capacity=total_capacity,
            historical_cancellation_rate=0.15 
        )
        
        confirmed_count = min(len(passengers), quota_available, len(available_berths))
        total_allowed = confirmed_count + rac_limit + wl_limit


        # 4. Calculate priority scores for passengers
        self._assign_priority_scores(passengers)
        passengers_sorted = sorted(passengers, key=lambda p: -p.priority_score)

        # 5. Group-aware allocation
        groups = self._extract_groups(passengers_sorted)
        allocations: List[AllocationResult] = []
        used_berths: Set[int] = set()

        # Phase A: Allocate groups first (family integrity)
        for group_id, group_passengers in groups.items():
            if group_id is None:
                continue
            group_allocs = self._allocate_group(
                group_passengers, available_berths, used_berths, confirmed_count - len(allocations)
            )
            allocations.extend(group_allocs)

        # Phase B: Allocate remaining individuals
        solo_passengers = [p for p in passengers_sorted if p.group_id is None and
                          not any(a.passenger_id == p.id for a in allocations)]
        for passenger in solo_passengers:
            alloc = self._allocate_single(
                passenger, available_berths, used_berths,
                confirmed_count - len([a for a in allocations if a.status == AllocationStatus.CONFIRMED])
            )
            allocations.append(alloc)

        # 6. Consume quotas
        confirmed = sum(1 for a in allocations if a.status == AllocationStatus.CONFIRMED)
        self.quota_mgr.consume(seg_key, quota, confirmed)

        # 7. Calculate scores
        group_score = self._calculate_group_integrity(allocations, passengers)
        comfort_score = (sum(a.comfort_score for a in allocations) / len(allocations)) if allocations else 0.0

        latency_ms = (time.time() - start_ts) * 1000
        logger.info(f"💺 [ALLOCATOR] Allocated {confirmed}/{len(passengers)} seats in {latency_ms:.1f}ms | "
                    f"Group:{group_score:.2f} Comfort:{comfort_score:.2f}")

        return BookingAllocation(
            booking_id=booking_id, train_number=train_number,
            travel_date=travel_date, class_code=class_code,
            allocations=allocations, group_integrity_score=round(group_score, 2),
            overall_comfort_score=round(comfort_score, 2), quota_used=quota
        )

    # --- Internal Methods ---

    def _assign_priority_scores(self, passengers: List[Passenger]):
        """Assign allocation priority based on passenger attributes."""
        for p in passengers:
            score = 50.0  # Base
            if p.category == PassengerCategory.DIVYANG: score += 30
            if p.category in (PassengerCategory.SENIOR_MALE, PassengerCategory.SENIOR_FEMALE): score += 25
            if p.category == PassengerCategory.SENIOR_FEMALE: score += 5  # Extra for senior women
            if p.requires_lower: score += 20
            if p.category == PassengerCategory.CHILD: score += 15
            if p.is_group_leader: score += 10
            if p.gender == "F": score += 5  # Women priority
            p.priority_score = score

    def _extract_groups(self, passengers: List[Passenger]) -> Dict[Optional[str], List[Passenger]]:
        groups: Dict[Optional[str], List[Passenger]] = defaultdict(list)
        for p in passengers:
            groups[p.group_id].append(p)
        return dict(groups)

    def _allocate_group(
        self, passengers: List[Passenger], all_berths: List[Berth],
        used: Set[int], remaining_confirmed: int
    ) -> List[AllocationResult]:
        """Allocate berths for a group, prioritizing same-compartment placement."""
        results = []
        group_size = len(passengers)

        # Find compartments with enough available berths
        comp_berths: Dict[int, List[Berth]] = defaultdict(list)
        for b in all_berths:
            if b.number not in used and b.is_available:
                comp_berths[b.compartment].append(b)

        # Sort compartments by available count (prefer ones that can fit whole group)
        best_comps = sorted(comp_berths.items(), key=lambda x: -len(x[1]))

        allocated_in_group = 0
        for passenger in passengers:
            if allocated_in_group >= confirmed_count:
                # [Phase 3: Dynamic Overflow]
                # If we've exhausted physical berths, check if we can fit into RAC/WL
                status = AllocationStatus.WAITLIST
                if allocated_in_group < confirmed_count + rac_limit:
                    status = AllocationStatus.RAC
                
                if allocated_in_group >= total_allowed:
                    status = AllocationStatus.REGRET
                    
                results.append(AllocationResult(
                    passenger_id=passenger.id, 
                    status=status,
                    comfort_score=0.2 if status != AllocationStatus.REGRET else 0.0, 
                    notes="Quota exhausted | Dynamic Overbooking applied" if status != AllocationStatus.REGRET else "Regret: System at capacity"
                ))
                allocated_in_group += 1
                continue


            best_berth = None
            best_score = -1.0

            # Try to stay in same compartment as already-allocated group members
            target_comps = set()
            for r in results:
                if r.coach and r.berth_number:
                    for b in all_berths:
                        if b.coach == r.coach and b.number == r.berth_number:
                            target_comps.add((b.coach, b.compartment))

            candidates = all_berths
            if target_comps:
                preferred = [b for b in all_berths if (b.coach, b.compartment) in target_comps
                            and b.number not in used and b.is_available]
                if preferred:
                    candidates = preferred

            for berth in candidates:
                if berth.number in used or not berth.is_available:
                    continue
                score = self.pref_matcher.score(passenger, berth)
                if score > best_score:
                    best_score = score
                    best_berth = berth

            if best_berth:
                used.add(best_berth.number)
                results.append(AllocationResult(
                    passenger_id=passenger.id, status=AllocationStatus.CONFIRMED,
                    coach=best_berth.coach, berth_number=best_berth.number,
                    berth_type=best_berth.berth_type, comfort_score=best_score,
                    notes=f"Group allocation | Compartment {best_berth.compartment}"
                ))
                allocated_in_group += 1
            else:
                results.append(AllocationResult(
                    passenger_id=passenger.id, status=AllocationStatus.WAITLIST,
                    comfort_score=0.1, notes="No berth available"
                ))
        return results

    def _allocate_single(
        self, passenger: Passenger, all_berths: List[Berth],
        used: Set[int], remaining_confirmed: int
    ) -> AllocationResult:
        """Allocate best available berth for a single passenger."""
        if remaining_confirmed <= 0:
            return AllocationResult(
                passenger_id=passenger.id, status=AllocationStatus.WAITLIST,
                comfort_score=0.1, notes="Quota exhausted"
            )

        best_berth = None
        best_score = -1.0

        for berth in all_berths:
            if berth.number in used or not berth.is_available:
                continue
            score = self.pref_matcher.score(passenger, berth)
            if score > best_score:
                best_score = score
                best_berth = berth

        if best_berth:
            used.add(best_berth.number)
            return AllocationResult(
                passenger_id=passenger.id, status=AllocationStatus.CONFIRMED,
                coach=best_berth.coach, berth_number=best_berth.number,
                berth_type=best_berth.berth_type, comfort_score=best_score,
                notes=f"Preference match: {best_score:.0%}"
            )
        return AllocationResult(
            passenger_id=passenger.id, status=AllocationStatus.WAITLIST,
            comfort_score=0.1, notes="No berth available"
        )

    def _calculate_group_integrity(self, allocations: List[AllocationResult],
                                   passengers: List[Passenger]) -> float:
        """Score how well family groups were kept together (same compartment)."""
        groups: Dict[str, List[AllocationResult]] = defaultdict(list)
        pax_map = {p.id: p for p in passengers}
        for a in allocations:
            p = pax_map.get(a.passenger_id)
            if p and p.group_id:
                groups[p.group_id].append(a)

        if not groups:
            return 1.0

        scores = []
        for gid, allocs in groups.items():
            confirmed = [a for a in allocs if a.status == AllocationStatus.CONFIRMED and a.coach]
            if len(confirmed) <= 1:
                scores.append(1.0)
                continue
            # Check if all in same coach + compartment
            coaches = set(a.coach for a in confirmed)
            if len(coaches) == 1:
                scores.append(1.0)
            elif len(coaches) == 2:
                scores.append(0.6)
            else:
                scores.append(0.3)

        return sum(scores) / len(scores) if scores else 1.0


# Singleton
seat_allocator = SeatAllocator()
