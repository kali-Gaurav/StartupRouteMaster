import struct
import logging
from sqlalchemy import text
import sys
import os

sys.path.append(os.path.join(os.getcwd(), 'backend'))
from database.session import SessionTransit as SessionLocal

def unpack_trains(blob):
    if not blob: return {}
    records = {}
    # Use V4 (16 bytes)
    for i in range(0, len(blob), 16):
        chunk = blob[i:i+16]
        if len(chunk) < 16: break
        unpacked = struct.unpack("IHHBBHf", chunk)
        tid = unpacked[0]
        records[tid] = unpacked
    return records

async def check_blobs():
    from core.container import container
    await container.get('db')
    db = SessionLocal()
    res = db.execute(text("SELECT station_code, length(transit_blob) FROM station_transit_index_bin WHERE station_code IN ('NDLS', 'MMCT')")).fetchall()
    for code, size in res:
        print(f"{code} blob size: {size} bytes")
    
    res = db.execute(text("SELECT station_code, transit_blob FROM station_transit_index_bin WHERE station_code IN ('NDLS', 'MMCT')")).fetchall()
    
    data = {r[0]: unpack_trains(r[1]) for r in res}
    
    ndls_trips = set(data.get('NDLS', {}).keys())
    mmct_trips = set(data.get('MMCT', {}).keys())
    
    print(f"NDLS trips in binary: {len(ndls_trips)}")
    print(f"MMCT trips in binary: {len(mmct_trips)}")
    
    common = ndls_trips.intersection(mmct_trips)
    print(f"Common trips: {common}")
    
    if common:
        query_weekday = 2 # Wednesday
        for tid in common:
            ndls_data = data['NDLS'][tid]
            mmct_data = data['MMCT'][tid]
            ndls_mask = ndls_data[3]
            src_day_offset = ndls_data[1] // 1440
            required_mask = (1 << ((query_weekday - src_day_offset) % 7))
            runs = (ndls_mask & required_mask) != 0
            dir_ok = ndls_data[4] < mmct_data[4]
            print(f"Trip {tid}: NDLS Seq {ndls_data[4]}, MMCT Seq {mmct_data[4]}, Mask {ndls_mask}, ReqMask {required_mask}, Runs {runs}, DirOK {dir_ok}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(check_blobs())
