#!/usr/bin/env python3
"""
Step 2 Debug Script: Database Connectivity Verification
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from backend.database import SessionLocal
from sqlalchemy import text
from backend.models import Segment, Station

def main():
    print("\n" + "="*70)
    print("DATABASE CONNECTIVITY TEST")
    print("="*70 + "\n")
    
    try:
        db = SessionLocal()
        print("✅ Database connection successful")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return
    
    # Test 1: Count segments
    print("\n[TEST 1] Count segments in database")
    print("-" * 70)
    try:
        segment_count = db.query(Segment).count()
        print(f"✅ Total segments: {segment_count}")
        
        if segment_count == 0:
            print("⚠️  WARNING: 0 segments found in database!")
            return
    except Exception as e:
        print(f"❌ Failed to count segments: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test 2: Count stations
    print("\n[TEST 2] Count stations in database")
    print("-" * 70)
    try:
        station_count = db.query(Station).count()
        print(f"✅ Total stations: {station_count}")
        
        if station_count == 0:
            print("⚠️  WARNING: 0 stations found in database!")
            return
    except Exception as e:
        print(f"❌ Failed to count stations: {e}")
        return
    
    # Test 3: Get first segment with full details
    print("\n[TEST 3] First verified segment with station details")
    print("-" * 70)
    try:
        segment = db.query(Segment).first()
        
        if segment:
            src_name = segment.source_station.name if segment.source_station else "UNKNOWN"
            dst_name = segment.dest_station.name if segment.dest_station else "UNKNOWN"
            
            print(f"Segment ID: {segment.id}")
            print(f"Source: {src_name} (ID: {segment.source_station_id})")
            print(f"Destination: {dst_name} (ID: {segment.dest_station_id})")
            print(f"Transport: {segment.transport_mode}")
            print(f"Duration: {segment.duration_minutes} mins")
            print(f"Cost: {segment.cost}")
            print(f"Operator: {segment.operator}")
            print(f"Departure: {segment.departure_time}, Arrival: {segment.arrival_time}")
            
            print(f"\n✅ VERIFIED TEST PAIR:")
            print(f"   Source: {src_name}")
            print(f"   Destination: {dst_name}")
        else:
            print("❌ No segments found")
            return
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n" + "="*70)
    print("✅ DATABASE CONNECTIVITY TEST COMPLETE")
    print("="*70 + "\n")
    
    db.close()

if __name__ == "__main__":
    main()

