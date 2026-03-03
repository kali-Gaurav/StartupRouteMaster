from database.session import SessionTransit
from sqlalchemy import text
import sys
import os

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

def check_multiple_corridors():
    s = SessionTransit()
    try:
        pairs = [
            ('NDLS', 'BCT'),
            ('NDLS', 'CSMT'),
            ('NDLS', 'HWH'),
            ('BCT', 'MAS'),
            ('NDLS', 'SBC')
        ]
        
        for src, dst in pairs:
            query = f"""
                SELECT count(*)
                FROM stop_times st1
                JOIN stop_times st2 ON st1.trip_id = st2.trip_id
                JOIN stops s1 ON st1.stop_id = s1.id
                JOIN stops s2 ON st2.stop_id = s2.id
                WHERE s1.code = '{src}' AND s2.code = '{dst}'
                AND st1.stop_sequence < st2.stop_sequence
            """
            count = s.execute(text(query)).scalar()
            print(f"Corridor {src} -> {dst}: {count} direct trains")
            
    finally:
        s.close()

if __name__ == "__main__":
    check_multiple_corridors()
