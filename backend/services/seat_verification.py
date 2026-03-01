import os
import aiohttp
import logging
import json
import asyncio
import uuid
from typing import Dict, Any, Optional
from core.redis import async_redis_client
from services.multi_layer_cache import multi_layer_cache, AvailabilityQuery
from datetime import datetime, date

logger = logging.getLogger(__name__)

# Request coalescing for seat checks
_inflight_seat_checks: Dict[str, asyncio.Future] = {}

class SeatVerificationService:
    """
    High-performance RapidIRCTC Seat Verification Service.
    Includes Async Caching, Persistent Sessions, and Request Coalescing.
    """
    _session: Optional[aiohttp.ClientSession] = None

    def __init__(self):
        self.api_key = os.getenv("RAPID_API_KEY") or os.getenv("RAPIDAPI_KEY", "")
        self.api_host = "irctc1.p.rapidapi.com"
        self.base_url = f"https://{self.api_host}/api/v1"

    @classmethod
    async def get_session(cls) -> aiohttp.ClientSession:
        if cls._session is None or cls._session.closed:
            cls._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
        return cls._session

    @classmethod
    async def close_session(cls):
        if cls._session and not cls._session.closed:
            await cls._session.close()
            cls._session = None

    async def check_segment(self, train_no: str, from_code: str, to_code: str, date_str: str, quota: str = "GN", class_type: str = "3A") -> Dict[str, Any]:
        """
        Sophisticated Seat Check:
        1. Redis L0/L1 Check
        2. Postgres L2 Check (Freshness aware)
        3. RapidAPI v1 (If needed) -> Save all 6 days to DB/Redis
        """
        await multi_layer_cache.initialize()
        
        try:
            # Handle both YYYY-MM-DD and DD-MM-YYYY
            if "-" in date_str and len(date_str.split("-")[0]) == 4:
                travel_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            else:
                travel_date = datetime.strptime(date_str, "%d-%m-%Y").date()
        except Exception:
            travel_date = datetime.utcnow().date()

        # 1. Hot Cache (Redis)
        query = AvailabilityQuery(
            train_id=int(train_no) if train_no.isdigit() else 0, 
            from_stop_id=abs(hash(from_code)) % 1000000, 
            to_stop_id=abs(hash(to_code)) % 1000000, 
            travel_date=travel_date, 
            quota_type=quota,
            class_type=class_type
        )
        cache_key = query.cache_key()
        
        cached = await multi_layer_cache.get_availability(query)
        if cached is not None:
            logger.info(f"🔥 Redis Hit: {train_no} availability")
            return cached

        # 2. Warm Cache (Postgres)
        from database.session import SessionLocal
        from database.models import TrainAvailabilityCache
        from sqlalchemy import and_
        
        db = SessionLocal()
        try:
            db_cache = db.query(TrainAvailabilityCache).filter(and_(
                TrainAvailabilityCache.train_number == train_no,
                TrainAvailabilityCache.from_station_code == from_code,
                TrainAvailabilityCache.to_station_code == to_code,
                TrainAvailabilityCache.journey_date == travel_date,
                TrainAvailabilityCache.class_type == class_type,
                TrainAvailabilityCache.quota == quota
            )).first()
            
            if db_cache:
                # Check freshness
                ttl = self._get_dynamic_ttl(travel_date)
                age = (datetime.utcnow() - db_cache.last_updated_at).total_seconds()
                if age < ttl:
                    logger.info(f"✨ Postgres Hit: {train_no} availability (Age: {age:.0f}s)")
                    return {
                        "available": "AVAILABLE" in db_cache.status_text.upper() or "AVL" in db_cache.status_text.upper(),
                        "status": db_cache.status_text,
                        "seats": db_cache.seats_available,
                        "fare": db_cache.fare,
                        "last_updated": db_cache.last_updated_at.isoformat()
                    }
        except Exception as e:
            logger.warning(f"Postgres cache lookup failed: {e}")
        finally:
            db.close()

        # 3. Request Coalescing (Single-Flight)
        if cache_key in _inflight_seat_checks:
            return await _inflight_seat_checks[cache_key]

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        _inflight_seat_checks[cache_key] = future

        try:
            # 4. RapidAPI Call (The actual source)
            # API expects DD-MM-YYYY
            api_date_str = travel_date.strftime("%d-%m-%Y")
            api_data = await self._execute_check_raw(train_no, from_code, to_code, api_date_str, quota, class_type)
            
            if api_data and api_data.get("status") and api_data.get("data"):
                # --- PERSIST ALL 6 DAYS (Bonus Cache Idea) ---
                asyncio.create_task(self._persist_bulk_availability(
                    train_no, from_code, to_code, quota, class_type, api_data["data"]
                ))
                
                # Extract the specific day's data from the response
                day_data = None
                for item in api_data["data"]:
                    try:
                        item_date_str = item.get("date")
                        item_date = self._parse_api_date(item_date_str)
                        if item_date == travel_date:
                            day_data = item
                            break
                    except: continue
                
                if not day_data and api_data["data"]:
                    day_data = api_data["data"][0]

                is_available = self._parse_availability_item(day_data)
                result = {
                    "available": is_available,
                    "status": day_data.get("current_status", "UNKNOWN") if day_data else "UNKNOWN",
                    "seats": day_data.get("seat_avl", 0) if day_data else 0,
                    "fare": day_data.get("total_fare", 0) if day_data else 0,
                    "timestamp": datetime.utcnow().isoformat()
                }
            else:
                result = {"available": True, "status": "UNKNOWN", "timestamp": datetime.utcnow().isoformat()}
            
            # Cache the requested day in Redis immediately
            await multi_layer_cache.set_availability(query, result)
                
            future.set_result(result)
            return result
        except Exception as e:
            if not future.done():
                future.set_exception(e)
            raise
        finally:
            if cache_key in _inflight_seat_checks:
                del _inflight_seat_checks[cache_key]

    def _get_dynamic_ttl(self, journey_date) -> int:
        days_left = (journey_date - datetime.utcnow().date()).days
        if days_left > 7: return 21600 # 6 hours
        if days_left > 2: return 7200  # 2 hours
        return 1800 # 30 min

    async def _execute_check_raw(self, train_no, from_code, to_code, date, quota, class_type) -> Optional[Dict]:
        if not self.api_key: return None
        url = f"{self.base_url}/checkSeatAvailability"
        headers = {"X-RapidAPI-Key": self.api_key, "X-RapidAPI-Host": self.api_host}
        params = {
            "trainNo": train_no, "fromStationCode": from_code, "toStationCode": to_code,
            "date": date, "quota": quota, "classType": class_type
        }
        session = await self.get_session()
        async with session.get(url, headers=headers, params=params) as resp:
            if resp.status == 200: return await resp.json()
        return None

    def _parse_api_date(self, d_str: str) -> date:
        """Robustly parse date from API response."""
        for fmt in ("%d-%m-%Y", "%d-%m-%Y", "%-d-%-m-%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(d_str, "%d-%m-%Y").date()
            except ValueError:
                continue
        parts = d_str.split("-")
        if len(parts) == 3:
            return date(int(parts[2]), int(parts[1]), int(parts[0]))
        raise ValueError(f"Cannot parse date: {d_str}")

    def _parse_availability_item(self, item: Optional[Dict]) -> bool:
        if not item: return True
        status_text = str(item.get("current_status", "")).upper()
        return any(x in status_text for x in ["AVAILABLE", "AVL", "RAC", "CURR"])

    def _parse_availability(self, data: Optional[Dict]) -> bool:
        """Legacy parser"""
        if not data or not data.get("status"): return True
        avail_list = data.get("data", [])
        if not avail_list: return True
        first = avail_list[0] if isinstance(avail_list, list) else avail_list
        return self._parse_availability_item(first)

    async def _persist_bulk_availability(self, train_no, from_code, to_code, quota, class_type, data_list):
        """Saves multiple days of availability to Postgres and Redis."""
        from database.session import SessionLocal, engine
        from database.models import TrainAvailabilityCache
        
        if not isinstance(data_list, list): data_list = [data_list]
        
        db = SessionLocal()
        try:
            dialect = engine.dialect.name
            logger.info(f"📋 Persisting bulk availability for {train_no} ({len(data_list)} days)")
            for item in data_list:
                try:
                    d_str = item.get("date")
                    j_date = self._parse_api_date(d_str)
                    status = item.get("current_status", "UNKNOWN")
                    
                    if dialect == "postgresql":
                        from sqlalchemy.dialects.postgresql import insert
                        stmt = insert(TrainAvailabilityCache).values(
                            id=str(uuid.uuid4()),
                            train_number=train_no,
                            from_station_code=from_code,
                            to_station_code=to_code,
                            journey_date=j_date,
                            class_type=class_type,
                            quota=quota,
                            status_text=status,
                            seats_available=item.get("seat_avl"),
                            fare=item.get("total_fare"),
                            last_updated_at=datetime.utcnow()
                        )
                        on_conflict_stmt = stmt.on_conflict_do_update(
                            constraint='uq_train_availability',
                            set_={
                                "status_text": status,
                                "seats_available": item.get("seat_avl"),
                                "fare": item.get("total_fare"),
                                "last_updated_at": datetime.utcnow()
                            }
                        )
                        db.execute(on_conflict_stmt)
                    else:
                        from sqlalchemy import and_
                        existing = db.query(TrainAvailabilityCache).filter(and_(
                            TrainAvailabilityCache.train_number == train_no,
                            TrainAvailabilityCache.from_station_code == from_code,
                            TrainAvailabilityCache.to_station_code == to_code,
                            TrainAvailabilityCache.journey_date == j_date,
                            TrainAvailabilityCache.class_type == class_type,
                            TrainAvailabilityCache.quota == quota
                        )).first()

                        if existing:
                            existing.status_text = status
                            existing.seats_available = item.get("seat_avl")
                            existing.fare = item.get("total_fare")
                            existing.last_updated_at = datetime.utcnow()
                        else:
                            new_cache = TrainAvailabilityCache(
                                id=str(uuid.uuid4()),
                                train_number=train_no,
                                from_station_code=from_code,
                                to_station_code=to_code,
                                journey_date=j_date,
                                class_type=class_type,
                                quota=quota,
                                status_text=status,
                                seats_available=item.get("seat_avl"),
                                fare=item.get("total_fare"),
                                last_updated_at=datetime.utcnow()
                            )
                            db.add(new_cache)
                    
                    # Also populate Redis for these adjacent days
                    query = AvailabilityQuery(
                        train_id=int(train_no) if train_no.isdigit() else 0,
                        from_stop_id=abs(hash(from_code)) % 1000000,
                        to_stop_id=abs(hash(to_code)) % 1000000,
                        travel_date=j_date,
                        quota_type=quota,
                        class_type=class_type
                    )
                    await multi_layer_cache.set_availability(query, {
                        "available": self._parse_availability_item(item),
                        "status": status,
                        "seats": item.get("seat_avl"),
                        "fare": item.get("total_fare"),
                        "timestamp": datetime.utcnow().isoformat()
                    })
                except Exception as ex: 
                    logger.debug(f"Failed to persist day {item.get('date')}: {ex}")
                    continue
            db.commit()
            logger.info(f"✅ Bulk Persisted {len(data_list)} days for {train_no}")
        except Exception as e:
            logger.error(f"Bulk persistence failure: {e}")
            db.rollback()
        finally:
            db.close()




    async def _execute_check(self, train_no: str, from_code: str, to_code: str, date: str, quota: str, class_type: str) -> bool:
        """Compatibility wrapper for legacy calls"""
        res = await self.check_segment(train_no, from_code, to_code, date, quota, class_type)
        return res.get("available", True)

    async def verify_journey(self, journey: dict) -> bool:
        """
        Loops through segments. 
        - If ANY train segment has no seats, the whole journey is marked UNAVAILABLE.
        - UPDATES the journey dictionary with LIVE FARES and STATUS from the API.
        """
        segments = journey.get("legs", journey.get("segments", []))
        
        tasks = []
        rail_segment_indices = []
        
        for idx, seg in enumerate(segments):
            if seg.get("mode", "").lower() not in ["rail", "train"]:
                continue
            
            train_no = seg.get("train_number")
            if not train_no: continue

            class_type = seg.get("class_type") or "3A"
            rail_segment_indices.append(idx)

            tasks.append(self.check_segment(
                train_no=train_no,
                from_code=seg.get("from_station_code", seg.get("from_station", "")),
                to_code=seg.get("to_station_code", seg.get("to_station", "")),
                date_str=seg.get("departure_time", seg.get("departure", "")).split("T")[0],
                class_type=class_type
            ))

        if not tasks:
            return True

        # Run all segment checks in parallel
        results = await asyncio.gather(*tasks)
        
        all_available = True
        total_live_cost = 0
        
        # Iterate through results and update the journey object in-place
        for i, res in enumerate(results):
            seg_idx = rail_segment_indices[i]
            segment = segments[seg_idx]
            
            # 1. Update Availability
            if not res.get("available", True):
                all_available = False
            
            # 2. Update Status Text for this segment
            segment["availability_status"] = res.get("status", "UNKNOWN")
            segment["seats_available"] = res.get("seats", 0)
            
            # 3. Update LIVE Fare (The API gives us the ground truth)
            live_fare = res.get("fare", 0)
            if live_fare > 0:
                segment["fare"] = live_fare
                total_live_cost += live_fare
            else:
                total_live_cost += segment.get("fare", 0)

        # Update the overall journey cost if we found live fares
        if total_live_cost > 0:
            journey["total_cost"] = total_live_cost
            journey["cheapest_fare"] = total_live_cost
            journey["availability_status"] = "AVAILABLE" if all_available else "UNAVAILABLE"

        return all_available

