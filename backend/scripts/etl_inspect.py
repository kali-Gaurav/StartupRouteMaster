from etl.sqlite_to_postgres import SQLiteReader, DEFAULT_SQLITE_PATH

r = SQLiteReader(DEFAULT_SQLITE_PATH)
segs = r.read_segment_data()
print('segments generated from sqlite:', len(segs))
print('sample segment:', segs[0] if segs else 'none')
sts = r.read_stations_master()
print('stations_master rows from sqlite:', len(sts))
print('sample station_master:', sts[0] if sts else 'none')
