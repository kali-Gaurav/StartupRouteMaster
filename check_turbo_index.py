
import sqlite3
import struct
import os

db_path = "backend/database/transit_graph.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

def unpack_v3(blob):
    if not blob: return {}
    records = {}
    record_size = 12
    fmt = "IHHBBH"
    for i in range(0, len(blob), record_size):
        chunk = blob[i:i+record_size]
        if len(chunk) < record_size: break
        unpacked = struct.unpack(fmt, chunk)
        tid, dep, arr, mask, seq, dist = unpacked
        records[tid] = {'mask': mask, 'seq': seq}
    return records

print("--- STATION TRANSIT INDEX BIN AUDIT ---")
for code in ['NDLS', 'BCT', 'MS', 'MAS']:
    cursor.execute("SELECT length(transit_blob) FROM station_transit_index_bin WHERE station_code = ?", (code,))
    row = cursor.fetchone()
    if row:
        print(f"Station {code}: Blob Size {row[0]}")
    else:
        print(f"Station {code}: NOT FOUND in binary index")

# Intersection Check for NDLS -> BCT
cursor.execute("SELECT transit_blob FROM station_transit_index_bin WHERE station_code = 'NDLS'")
ndls_blob = cursor.fetchone()[0]
cursor.execute("SELECT transit_blob FROM station_transit_index_bin WHERE station_code = 'BCT'")
bct_blob = cursor.fetchone()[0]

ndls_trains = unpack_v3(ndls_blob)
bct_trains = unpack_v3(bct_blob)

common = set(ndls_trains.keys()).intersection(bct_trains.keys())
print(f"\nCommon Trip IDs (Raw) for NDLS->BCT: {len(common)}")

for tid in common:
    s = ndls_trains[tid]
    d = bct_trains[tid]
    print(f"  TID {tid}: NDLS_Seq={s['seq']}, BCT_Seq={d['seq']}, Mask={s['mask']}")

conn.close()
