import asyncio
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from core.route_engine import route_engine
from core.route_engine.constraints import RouteConstraints
from services.seat_verification import SeatVerificationService
from database.session import SessionLocal


async def verify_ndls_bct_for_next_7_days():
    """
    Simple diagnostic script that:
    - runs the RouteEngine (FastRouter + HybridRAPTOR) for NDLS->BCT
    - for each day in the next 7 days
    - and uses RapidAPI-backed SeatVerificationService to check if at least one route
      corresponds to a running train with any availability.
    This is meant for manual debugging, not for automated CI.
    """
    db: Session = SessionLocal()
    seat_svc = SeatVerificationService()

    try:
        today = datetime.utcnow().date()
        for offset in range(0, 7):
            journey_date = today + timedelta(days=offset)
            dt = datetime.combine(journey_date, datetime.min.time()).replace(hour=8, minute=0)
            print(f"\n=== NDLS -> BCT on {journey_date} ===")

            constraints = RouteConstraints(
                max_transfers=3,
                range_minutes=1440,
                max_results=15,
            )
            routes = await route_engine.search_routes("NDLS", "BCT", dt, constraints)
            print(f"Engine returned {len(routes)} routes.")
            if not routes:
                continue

            # Check first few routes for live availability
            for idx, r in enumerate(routes[:5]):
                if not r.segments:
                    continue
                first_seg = r.segments[0]
                train_no = first_seg.train_number
                from_code = first_seg.departure_code
                to_code = first_seg.arrival_code
                date_str = journey_date.strftime("%Y-%m-%d")
                res = await seat_svc.check_segment(train_no, from_code, to_code, date_str)
                print(
                    f"Route {idx}: train {train_no} {from_code}->{to_code} "
                    f"status={res.get('status')} seats={res.get('seats')} success={res.get('success')}"
                )
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(verify_ndls_bct_for_next_7_days())

