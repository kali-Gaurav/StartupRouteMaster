import sqlite3
import math
import asyncio
import aiohttp
import json
import logging
import time

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("EnrichmentPipeline")

DB_PATH = "backend/database/transit_graph.db"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "RouteMaster-DataEnrichment/3.0"

def haversine(lat1, lon1, lat2, lon2):
    if not all([lat1, lon1, lat2, lon2]) or (lat1==0.0 and lon1==0.0) or (lat2==0.0 and lon2==0.0): 
        return 0.0
    try:
        lat1, lon1, lat2, lon2 = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
        val = math.cos(lat1)*math.cos(lat2)*math.cos(lon2-lon1) + math.sin(lat1)*math.sin(lat2)
        val = max(-1.0, min(1.0, val))
        return round(6371 * math.acos(val), 2)
    except Exception:
        return 0.0

def calc_duration(dep_time, arr_time):
    try:
        h1, m1, _ = map(int, str(dep_time).split(':'))
        h2, m2, _ = map(int, str(arr_time).split(':'))
        t1 = h1 * 60 + m1
        t2 = h2 * 60 + m2
        if t2 < t1: t2 += 1440
        return t2 - t1
    except:
        return 0

async def fetch_all_india_stations(session):
    """
    BATCH FETCH: Gets thousands of stations in one API call from Overpass.
    """
    logger.info("📡 Batch downloading all Indian Railway Stations from OpenStreetMap...")
    
    # Query for all nodes tagged as railway=station in India
    query = """
    [out:json][timeout:90];
    area["name"="India"]["admin_level"="2"]->.searchArea;
    (
      node["railway"="station"](area.searchArea);
      node["railway"="halt"](area.searchArea);
    );
    out body;
    """
    
    try:
        async with session.post(OVERPASS_URL, data={"data": query}, headers={"User-Agent": USER_AGENT}) as resp:
            if resp.status != 200:
                logger.error(f"Overpass Error: {resp.status}")
                return []
            data = await resp.json()
            elements = data.get("elements", [])
            logger.info(f"✅ Downloaded {len(elements)} stations from OSM.")
            return elements
    except Exception as e:
        logger.error(f"Overpass Connection Failed: {e}")
        return []

async def run_pipeline():
    logger.info("🚀 Starting Master Data Enrichment Pipeline (BATCH MODE)...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # PHASE 1: Local Math (Same as before, very fast)
    logger.info("⚡ PHASE 1: Recomputing all Segment Distances & Durations locally...")
    cursor.execute("SELECT id, latitude, longitude FROM stops")
    stop_coords = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
    cursor.execute("SELECT id, source_station_id, dest_station_id, departure_time, arrival_time FROM segments")
    segments = cursor.fetchall()
    updates = []
    for seg_id, src_id, dst_id, dep_time, arr_time in segments:
        src_lat, src_lon = stop_coords.get(int(src_id), (0.0, 0.0))
        dst_lat, dst_lon = stop_coords.get(int(dst_id), (0.0, 0.0))
        dist = haversine(src_lat, src_lon, dst_lat, dst_lon)
        updates.append((round(dist * 1.2, 2), calc_duration(dep_time, arr_time), 100 if dist > 0 else 0, seg_id))
    cursor.executemany("UPDATE segments SET distance_km=?, duration_minutes=?, data_quality_score=? WHERE id=?", updates)
    conn.commit()

    # PHASE 2: BATCH COORDINATE REPAIR
    logger.info("🌐 PHASE 2: Batch Repairing Station Coordinates via Overpass...")
    
    async with aiohttp.ClientSession() as session:
        osm_data = await fetch_all_india_stations(session)
        if not osm_data:
            logger.warning("Falling back to legacy slow mode...")
            return

        # Build a lookup map from OSM: Name -> (lat, lon)
        # We normalize names to uppercase for better matching
        osm_lookup = {}
        for el in osm_data:
            tags = el.get("tags", {})
            name = tags.get("name", "").upper()
            ref = tags.get("ref", "").upper() # Often contains the station code (e.g., NDLS)
            
            if name: osm_lookup[name] = (el["lat"], el["lon"])
            if ref: osm_lookup[ref] = (el["lat"], el["lon"])

        cursor.execute("SELECT id, name, code FROM stops WHERE latitude=0.0 OR longitude=0.0")
        missing = cursor.fetchall()
        logger.info(f"Analyzing {len(missing)} stations with missing coordinates...")

        coord_updates = []
        matched_count = 0
        for sid, name, code in missing:
            # 1. Try exact code match
            coords = osm_lookup.get(code.upper())
            # 2. Try exact name match
            if not coords:
                coords = osm_lookup.get(name.upper())
            # 3. Try name containing "Railway Station"
            if not coords:
                coords = osm_lookup.get(f"{name.upper()} RAILWAY STATION")

            if coords:
                coord_updates.append((coords[0], coords[1], sid))
                matched_count += 1
        
        if coord_updates:
            cursor.executemany("UPDATE stops SET latitude=?, longitude=? WHERE id=?", coord_updates)
            conn.commit()
            logger.info(f"✅ Repaired {matched_count} stations instantly using batch data.")

    # PHASE 4: Score Generation
    cursor.execute("UPDATE stops SET data_quality_score=40 WHERE latitude != 0.0")
    cursor.execute("UPDATE stops SET data_quality_score=data_quality_score+30 WHERE city IS NOT NULL AND city != ''")
    conn.commit()
    conn.close()
    logger.info("🎉 Master Data Enrichment Completed Successfully!")

if __name__ == "__main__":
    asyncio.run(run_pipeline())
