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
        logger.info("Starting Memory-Efficient Schedule Compilation...")
        db = SessionLocal()
        try:
            # 1. Fetch all stops (Still needed in RAM for mapping, but we use scalars for speed)
            stop_ids = [s for s in db.query(Stop.id).order_by(Stop.id).scalars().all()]
            stop_map = {stop_id: i for i, stop_id in enumerate(stop_ids)}
            id_to_stop = {i: stop_id for i, stop_id in enumerate(stop_ids)}
            
            # 2. Fetch all connections (Segments) using yield_per for streaming
            # Subtask 2.5: Streaming large query
            connection_data = []
            
            query = db.query(Segment).execution_options(yield_per=500)
            
            for seg in query:
                try:
                    dep_ts = int(seg.departure_time.hour * 3600 + seg.departure_time.minute * 60)
                    arr_ts = int(seg.arrival_time.hour * 3600 + seg.arrival_time.minute * 60)
                    
                    if arr_ts < dep_ts:
                        arr_ts += 86400

                    connection_data.append([
                        stop_map[seg.source_station_id],
                        stop_map[seg.dest_station_id],
                        dep_ts,
                        arr_ts,
                        seg.trip_id
                    ])
                except KeyError as ke:
                    logger.warning(f"Skipping segment {seg.id}: Station mapping error for {ke}")
                    continue

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
