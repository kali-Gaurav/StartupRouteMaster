import sqlite3
import struct
import os

db_path = 'database/transit_graph.db'
if not os.path.exists(db_path):
    db_path = '../database/transit_graph.db'

conn = sqlite3.connect(db_path)
blob = conn.execute("SELECT transit_blob FROM station_transit_index_bin WHERE station_code='NDLS'").fetchone()[0]
print(f"NDLS Blob Size: {len(blob)}")

_V3_STRUCT = struct.Struct("IHHBBH")
_V4_STRUCT = struct.Struct("IHHBBHf")

def unpack_all(blob):
    if not blob: return {}
    records = {}
    size = len(blob)
    if size % 16 == 0: struct_type, r_size = _V4_STRUCT, 16
    elif size % 12 == 0: struct_type, r_size = _V3_STRUCT, 12
    else: return {}
    for i in range(0, size, r_size):
        chunk = blob[i:i+r_size]
        unpacked = struct_type.unpack(chunk)
        tid = unpacked[0]
        records[tid] = unpacked
    return records

records = unpack_all(blob)
print(f"NDLS Records: {len(records)}")
print("Sample NDLS TIDs:", sorted(list(records.keys()))[:10])

blob2 = conn.execute("SELECT transit_blob FROM station_transit_index_bin WHERE station_code='MMCT'").fetchone()[0]
print(f"MMCT Blob Size: {len(blob2)}")
records2 = unpack_all(blob2)
print(f"MMCT Records: {len(records2)}")

common = set(records.keys()).intersection(records2.keys())
print(f"Common TIDs: {common}")

conn.close()
