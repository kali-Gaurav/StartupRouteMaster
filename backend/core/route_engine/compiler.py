import numpy as np
import logging
import os
from datetime import datetime, timedelta
from database.session import SessionLocal
from database.models import StopTime, Trip, Stop, Segment

logger = logging.getLogger(__name__)

class ScheduleCompiler:
    """
    Compiles the relational database schedule into a compact, 
    memory-mapped NumPy binary for the CSA routing kernel.
    """
    def __init__(self, output_path: str = "backend/data/timetable.npz"):
        self.output_path = output_path
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)

    def compile(self):
        logger.info("Starting Schedule Compilation for CSA Kernel...")
        db = SessionLocal()
        try:
            # 1. Fetch all stops and create an integer mapping
            stops = db.query(Stop).all()
            stop_map = {s.id: i for i, s in enumerate(sorted([st.id for st in stops]))}
            id_to_stop = {i: s.id for s, i in stop_map.items()}
            
            # 2. Fetch all connections (Segments)
            # A 'Connection' in CSA is a (dep_stop, arr_stop, dep_time, arr_time, trip_id)
            segments = db.query(Segment).all()
            
            # Convert to a flat NumPy array
            # Format: [dep_stop_idx, arr_stop_idx, dep_ts, arr_ts, trip_id]
            # Times are stored as Unix timestamps (int) for speed
            connection_data = []
            
            # Base date for timestamp normalization (to keep integers small)
            base_date = datetime(2024, 1, 1)

            for seg in segments:
                # Note: In a real system, we'd handle multi-day calendars here
                # For the fast kernel, we normalize all times to a 24h or multi-day window
                dep_ts = int(seg.departure_time.hour * 3600 + seg.departure_time.minute * 60)
                arr_ts = int(seg.arrival_time.hour * 3600 + seg.arrival_time.minute * 60)
                
                # Handle overnight trains
                if arr_ts < dep_ts:
                    arr_ts += 86400

                connection_data.append([
                    stop_map[seg.source_stop_id],
                    stop_map[seg.destination_stop_id],
                    dep_ts,
                    arr_ts,
                    seg.trip_id
                ])

            # 3. Sort connections by departure time (Requirement for CSA)
            connections = np.array(connection_data, dtype=np.int32)
            connections = connections[connections[:, 2].argsort()]

            # 4. Save metadata and packed arrays
            np.savez_compressed(
                self.output_path,
                connections=connections,
                stop_ids=np.array(list(id_to_stop.values()), dtype=np.int32),
                stop_indices=np.array(list(stop_map.values()), dtype=np.int32)
            )
            
            logger.info(f"Compilation complete. {len(connections)} connections saved to {self.output_path}")
            return True
        except Exception as e:
            logger.error(f"Compilation failed: {e}")
            return False
        finally:
            db.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    compiler = ScheduleCompiler()
    compiler.compile()
