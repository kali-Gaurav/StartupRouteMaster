import sqlite3
import struct

_V3_STRUCT = struct.Struct("IHHBBH")
_V4_STRUCT = struct.Struct("IHHBBHf")

def unpack_trains(blob):
    if not blob: return {}
    records, size = {}, len(blob)
    if size % 16 == 0: struct_type, r_size = _V4_STRUCT, 16
    elif size % 12 == 0: struct_type, r_size = _V3_STRUCT, 12
    else: return {}
    for i in range(0, size, r_size):
        chunk = blob[i:i+r_size]
        try:
            unpacked = struct_type.unpack(chunk)
            tid, dep, arr, mask, seq, dist = unpacked[:6]
            records[tid] = {'dep': dep, 'arr': arr, 'mask': mask, 'seq': seq, 'dist': dist, 'price': unpacked[6] if r_size == 16 else 0}
        except: continue
    return records

def dump_station(code):
    conn = sqlite3.connect('backend/database/transit_graph.db')
    row = conn.execute("SELECT transit_blob FROM station_transit_index_bin WHERE station_code = ?", (code,)).fetchone()
    if not row:
        print(f"No data for {code}")
        return
    trains = unpack_trains(row[0])
    print(f"Trains for {code}: {len(trains)}")
    # Print first 5
    for i, (tid, data) in enumerate(trains.items()):
        if i >= 5: break
        print(f"  Train {tid}: {data}")
    conn.close()

if __name__ == "__main__":
    dump_station('NDLS')
    dump_station('MMCT')
