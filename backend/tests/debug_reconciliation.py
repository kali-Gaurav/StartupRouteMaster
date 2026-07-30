from database.session import SessionLocal
from database.models import Booking, EscrowStatus
from datetime import datetime, date
from sqlalchemy import func

def debug_recon():
    db = SessionLocal()
    target_date = date.today()
    start_str = target_date.strftime("%Y-%m-%d 00:00:00")
    end_str = target_date.strftime("%Y-%m-%d 23:59:59")
    
    print(f"DEBUG: Searching between '{start_str}' and '{end_str}'")
    
    # 1. Inspect raw bookings
    all_bookings = db.query(Booking).all()
    print(f"DEBUG: Total Bookings in DB: {len(all_bookings)}")
    
    for b in all_bookings:
        # Get type of created_at
        print(f"  Booking {b.id}: created_at='{b.created_at}' (Type: {type(b.created_at)}) status={b.escrow_status}")
        
    # 2. Check manual query
    count = db.query(Booking).filter(
        Booking.created_at >= start_str,
        Booking.created_at <= end_str
    ).count()
    print(f"DEBUG: Count with string comparison: {count}")
    
    # 3. Check with func.date
    count_date = db.query(Booking).filter(
        func.date(Booking.created_at) == target_date.isoformat()
    ).count()
    print(f"DEBUG: Count with func.date: {count_date}")

if __name__ == "__main__":
    debug_recon()
