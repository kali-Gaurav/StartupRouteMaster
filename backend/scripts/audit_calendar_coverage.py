"""
[Missing Logic #2] audit_calendar_coverage.py

Finds trips whose service_id is either:
1. Completely missing from both 'calendar' and 'calendar_dates' tables.
2. Inactive for a specific target date/range due to missing service patterns.

Usage:
    python backend/scripts/audit_calendar_coverage.py --date 2026-03-01
    python backend/scripts/audit_calendar_coverage.py --start 2026-03-01 --end 2026-03-07
"""

import sys
import os
import argparse
from datetime import datetime, timedelta, date
from sqlalchemy import and_, or_, not_

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from database.session import SessionLocal
from database.models import Trip, Calendar, CalendarDate

def get_day_name(target_date: date) -> str:
    return target_date.strftime('%A').lower()

def audit_coverage(session, start_date: date, end_date: date):
    print(f"Auditing calendar coverage from {start_date} to {end_date}...")
    
    # 1. Find COMPLETELY missing service_ids (never defined anywhere)
    # These are critical ETL failures.
    all_service_ids_in_trips = session.query(Trip.service_id).distinct().all()
    all_service_ids_in_trips = {r[0] for r in all_service_ids_in_trips}
    
    cal_service_ids = {r[0] for r in session.query(Calendar.service_id).all()}
    cal_date_service_ids = {r[0] for r in session.query(CalendarDate.service_id).distinct().all()}
    
    defined_service_ids = cal_service_ids.union(cal_date_service_ids)
    completely_missing = all_service_ids_in_trips - defined_service_ids
    
    if completely_missing:
        print(f"\n[CRITICAL] Found {len(completely_missing)} service_ids completely missing from both tables:")
        for sid in sorted(list(completely_missing)):
            trip_count = session.query(Trip).filter(Trip.service_id == sid).count()
            print(f"  - service_id: {sid} ({trip_count} trips affected)")
    else:
        print("\n[OK] No service_ids are completely missing from the database.")

    # 2. Daily coverage audit
    curr = start_date
    while curr <= end_date:
        day_name = get_day_name(curr)
        print(f"\n--- Audit for {curr.isoformat()} ({day_name}) ---")
        
        # Subquery for service_ids that are ACTIVE on this date in 'calendar'
        # ACTIVE = (start <= date <= end) AND (day_flag is True)
        active_in_cal = session.query(Calendar.service_id).filter(
            and_(
                Calendar.start_date <= curr,
                Calendar.end_date >= curr,
                getattr(Calendar, day_name) == True
            )
        ).subquery()
        
        # Subquery for service_ids with EXCEPTIONS on this date
        # Added (1) or Removed (2)
        added_exceptions = session.query(CalendarDate.service_id).filter(
            and_(
                CalendarDate.date == curr,
                CalendarDate.exception_type == 1
            )
        ).subquery()
        
        removed_exceptions = session.query(CalendarDate.service_id).filter(
            and_(
                CalendarDate.date == curr,
                CalendarDate.exception_type == 2
            )
        ).subquery()
        
        # A trip is active if:
        # (it is in active_in_cal AND NOT in removed_exceptions)
        # OR (it is in added_exceptions)
        
        # We want to find trips that are NOT active
        inactive_trips = session.query(Trip).filter(
            not_(
                or_(
                    and_(
                        Trip.service_id.in_(active_in_cal),
                        Trip.service_id.not_in(removed_exceptions)
                    ),
                    Trip.service_id.in_(added_exceptions)
                )
            )
        ).all()
        
        if inactive_trips:
            print(f"Found {len(inactive_trips)} trips inactive on this date.")
            # Group by service_id for cleaner output
            by_sid = {}
            for t in inactive_trips:
                by_sid.setdefault(t.service_id, []).append(t.trip_id)
            
            for sid, trip_ids in by_sid.items():
                print(f"  service_id: {sid} -> {len(trip_ids)} trips affected (e.g., {trip_ids[0]})")
        else:
            print("All trips have valid service coverage for this date.")
            
        curr += timedelta(days=1)

def main():
    parser = argparse.ArgumentParser(description="Audit GTFS calendar coverage.")
    parser.add_argument("--date", help="Target date (YYYY-MM-DD)")
    parser.add_argument("--start", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", help="End date (YYYY-MM-DD)")
    
    args = parser.parse_args()
    
    if args.date:
        start_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        end_date = start_date
    elif args.start and args.end:
        start_date = datetime.strptime(args.start, "%Y-%m-%d").date()
        end_date = datetime.strptime(args.end, "%Y-%m-%d").date()
    else:
        # Default to today
        start_date = date.today()
        end_date = start_date

    session = SessionLocal()
    try:
        audit_coverage(session, start_date, end_date)
    finally:
        session.close()

if __name__ == "__main__":
    main()
