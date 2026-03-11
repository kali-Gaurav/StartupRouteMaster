import sqlite3
import os

db_path = 'backend/database/transit_graph.db'

def verify_task_1():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    report = ["--- TASK 1 VERIFICATION REPORT ---"]
    
    # 1. Stops & Clusters
    cursor.execute("SELECT count(*) FROM stops")
    stops_count = cursor.fetchone()[0]
    cursor.execute("SELECT count(*) FROM city_clusters")
    clusters_count = cursor.fetchone()[0]
    report.append(f"Stops: {stops_count}")
    report.append(f"Clusters: {clusters_count} (Avg {stops_count/clusters_count:.2f} stops/cluster)")
    
    # 2. Graph Density (Segments & Stop Times)
    cursor.execute("SELECT count(*) FROM segments")
    segments_count = cursor.fetchone()[0]
    cursor.execute("SELECT count(*) FROM stop_times")
    st_count = cursor.fetchone()[0]
    report.append(f"Segments: {segments_count}")
    report.append(f"Stop Times: {st_count}")
    
    # 3. Distance & Duration Accuracy
    cursor.execute("SELECT avg(distance_km), max(distance_km), min(distance_km) FROM segments")
    dist_stats = cursor.fetchone()
    report.append(f"Avg Distance: {dist_stats[0]:.2f} km (Max: {dist_stats[1]}, Min: {dist_stats[2]})")
    
    cursor.execute("SELECT avg(duration_minutes), max(duration_minutes), min(duration_minutes) FROM segments")
    dur_stats = cursor.fetchone()
    report.append(f"Avg Duration: {dur_stats[0]:.2f} min (Max: {dur_stats[1]}, Min: {dur_stats[2]})")

    # 4. Data Quality
    cursor.execute("SELECT avg(data_quality_score) FROM stops")
    stop_dq = cursor.fetchone()[0]
    report.append(f"Avg Station Data Quality: {stop_dq:.2f}")

    # 5. Transfers
    cursor.execute("SELECT count(*) FROM transfers")
    trans_count = cursor.fetchone()[0]
    report.append(f"Transfer Edges: {trans_count}")

    # 6. Integrity Check
    cursor.execute("SELECT count(*) FROM stop_times WHERE trip_id NOT IN (SELECT id FROM trips)")
    orphan_st = cursor.fetchone()[0]
    report.append(f"Orphan Stop Times: {orphan_st}")

    print("\n".join(report))
    conn.close()

if __name__ == "__main__":
    verify_task_1()
