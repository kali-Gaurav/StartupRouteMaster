import sqlite3
import struct
import os

db_path = 'database/transit_graph.db'
if not os.path.exists(db_path):
    db_path = '../database/transit_graph.db'
conn = sqlite3.connect(db_path)

blob = conn.execute("SELECT transit_blob FROM station_transit_index_bin WHERE station_code='NDLS'").fetchone()[0]
_V3_STRUCT = struct.Struct("IHHBBH")
_V4_STRUCT = struct.Struct("IHHBBHf")

def unpack_all(blob):
    records = {}
    size = len(blob)
    r_size = 16 if size % 16 == 0 else 12
    struct_type = _V4_STRUCT if r_size == 16 else _V3_STRUCT
    for i in range(0, size, r_size):
        chunk = blob[i:i+r_size]
        unpacked = struct_type.unpack(chunk)
        records[unpacked[0]] = unpacked
    return records

records = unpack_all(blob)
print(f"Is 2003 in NDLS? {2003 in records}")

# Check 12952 (Trips table ID might not be 12952)
res = conn.execute("SELECT id FROM trips WHERE trip_id='12952'").fetchone()
if res:
    tid = res[0]
    print(f"Trip 12952 ID: {tid}")
    print(f"Is {tid} in NDLS? {tid in records}")
else:
    print("Trip 12952 not found in trips table.")

conn.close()
