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
            records[tid] = {'dep': dep, 'arr': arr, 'mask': mask, 'seq': seq, 'dist': dist}
        except: continue
    return records

def check_direct(src, dst):
    conn = sqlite3.connect('backend/database/transit_graph.db')
    b1 = conn.execute("SELECT transit_blob FROM station_transit_index_bin WHERE station_code = ?", (src,)).fetchone()
    b2 = conn.execute("SELECT transit_blob FROM station_transit_index_bin WHERE station_code = ?", (dst,)).fetchone()
    if not b1 or not b2:
        print("Missing blob")
        return
    
    t1 = unpack_trains(b1[0])
    t2 = unpack_trains(b2[0])
    
    common = set(t1.keys()).intersection(t2.keys())
    print(f"Common trips between {src} and {dst}: {len(common)}")
    
    for tid in common:
        s = t1[tid]
        d = t2[tid]
        if s['seq'] < d['seq']:
            print(f"  Valid Train {tid}: Seq {s['seq']} -> {d['seq']}, Mask {s['mask']}, Dep {s['dep']}")
            # Check mask for Thursday (3)
            src_day_offset = s['dep'] // 1440
            req_mask = (1 << ((3 - src_day_offset) % 7))
            if s['mask'] & req_mask:
                print(f"    MATCHES THURSDAY! (req_mask {req_mask})")
            else:
                print(f"    No match for Thursday (req_mask {req_mask})")
    conn.close()

if __name__ == "__main__":
    check_direct('NDLS', 'CSMT')
