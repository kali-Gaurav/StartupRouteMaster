import sqlite3
import math
import os
import uuid

db_path = 'backend/database/transit_graph.db'

def haversine(lat1, lon1, lat2, lon2):
    R = 6371 # Earth radius in km
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat / 2) * math.sin(dLat / 2) + \
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
        math.sin(dLon / 2) * math.sin(dLon / 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def parse_time_to_minutes(time_str):
    h, m, s = map(int, time_str.split(':'))
    return h * 60 + m

def calculate_duration(dep_time, arr_time):
    dep_m = parse_time_to_minutes(dep_time)
    arr_m = parse_time_to_minutes(arr_time)
    duration = arr_m - dep_m
    if duration < 0:
        duration += 1440 
    return duration

def generate_segments():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Clearing existing segments...")
    cursor.execute("DELETE FROM segments")

    print("Caching station coordinates...")
    station_map = {row[0]: {'lat': row[1], 'lon': row[2], 'code': row[3]} for row in cursor.execute("SELECT id, latitude, longitude, code FROM stops").fetchall()}

    print("Caching train numbers from trips...")
    cursor.execute("SELECT id, trip_id FROM trips")
    trip_to_train = {row[0]: row[1] for row in cursor.fetchall()}

    print("Fetching stop_times grouped by trip...")
    cursor.execute("SELECT trip_id, stop_id, departure_time, arrival_time, stop_sequence FROM stop_times ORDER BY trip_id, stop_sequence")
    
    current_trip_id = None
    prev_stop = None
    segments_to_insert = []
    
    all_stop_times = cursor.fetchall()
    print(f"Processing {len(all_stop_times)} stop_times with Dwell Time correction...")

    for row in all_stop_times:
        trip_id, stop_id, dep_time, arr_time, seq = row
        
        if trip_id != current_trip_id:
            current_trip_id = trip_id
            prev_stop = row
            continue
        
        # Segment is from PREV_STOP's DEPARTURE to CURRENT_STOP's ARRIVAL (Travel Time)
        # BUT: To make Sum(Segments) == Total Trip Duration, 
        # we must include the dwell time at the STARTING station of the segment.
        
        # Formula for total trip duration: StopTimes[Last].Arrival - StopTimes[0].Departure
        # Our segments must be:
        # Seg 1: [Stop 0 Arrival -> Stop 1 Arrival] (Includes Dwell at 0 + Travel 0-1)
        # Actually, standard graph logic is:
        # Segment(A->B) duration = B.Arrival - A.Arrival
        
        p_trip_id, p_stop_id, p_dep_time, p_arr_time, p_seq = prev_stop
        
        source = station_map.get(p_stop_id)
        dest = station_map.get(stop_id)
        
        if source and dest:
            dist = haversine(source['lat'], source['lon'], dest['lat'], dest['lon'])
            
            # Corrected duration: Time from previous station arrival to current station arrival
            # This ensures that Sum(Segment Durations) = Total Trip Time.
            # Segment duration = Current_Arrival - Prev_Arrival
            duration = calculate_duration(p_arr_time, arr_time)
            
            train_num = trip_to_train.get(trip_id, "00000")
            
            segments_to_insert.append((
                str(uuid.uuid4()),
                trip_id,
                p_stop_id,
                stop_id,
                p_dep_time,
                arr_time,
                duration,
                round(dist, 2),
                train_num,
                0
            ))
        
        prev_stop = row
        
        if len(segments_to_insert) >= 5000:
            cursor.executemany(
                "INSERT INTO segments (id, trip_id, source_stop_id, dest_station_id, departure_time, arrival_time, duration_minutes, distance_km, train_number, data_quality_score) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                segments_to_insert
            )
            segments_to_insert = []

    if segments_to_insert:
        cursor.executemany(
            "INSERT INTO segments (id, trip_id, source_stop_id, dest_station_id, departure_time, arrival_time, duration_minutes, distance_km, train_number, data_quality_score) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            segments_to_insert
        )

    conn.commit()
    conn.close()
    print("Segments generation with Dwell Time Correction Complete!")

if __name__ == "__main__":
    generate_segments()
