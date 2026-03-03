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

# Request coalescing for seat checks to prevent parallel duplicate calls
_inflight_seat_checks: Dict[str, asyncio.Future] = {}

class SeatVerificationService:
    """
    Quota-Optimized RapidIRCTC Seat Verification Service.
    Uses api/v2 for bulk availability and aggressive multi-layer caching.
    """
    _session: Optional[aiohttp.ClientSession] = None

    # class-level cache of detected version (shared across instances)
    _detected_version: Optional[str] = None

    def __init__(self):
        self.api_key = os.getenv("RAPID_API_KEY") or os.getenv("RAPIDAPI_KEY", "")
        self.api_host = "irctc1.p.rapidapi.com"
        # optional override from config
        from database.config import Config
        pref = getattr(Config, "RAPIDAPI_PREFERRED_VERSION", "")
        self.preferred_version = pref.lower() if pref else None
        self.base_url_v3 = f"https://{self.api_host}/api/v3"
        self.base_url_v2 = f"https://{self.api_host}/api/v2"
        self.base_url_v1 = f"https://{self.api_host}/api/v1"

        # proactively detect version in background so first user request isn't slowed
        if not SeatVerificationService._detected_version:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._detect_working_version())
            except RuntimeError:
                # not in an event loop yet; detection will occur on first call
                pass

    @classmethod
    async def get_session(cls) -> aiohttp.ClientSession:
        if cls._session is None or cls._session.closed:
            # 120s total timeout for the entire session
            cls._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120))
        return cls._session

    @classmethod
    async def close_session(cls):
        if cls._session and not cls._session.closed:
            await cls._session.close()
            cls._session = None

    async def _detect_working_version(self) -> str:
        """Determine which API version actually responds successfully.
        Result is cached in the class variable so subsequent calls skip detection.
        The detection flow honours the configured `preferred_version` override if set.
        """
        if SeatVerificationService._detected_version:
            return SeatVerificationService._detected_version
        # honour explicit override first
        if self.preferred_version in ("v3", "v2", "v1"):
            SeatVerificationService._detected_version = self.preferred_version
            logger.debug(f"Using preferred RapidAPI version {self.preferred_version}")
            return SeatVerificationService._detected_version

        # simple probe using a known train/date that has given data in the past
        probe_params = {
            "trainNo": "16378", "fromStationCode": "PGT", "toStationCode": "BNC",
            "date": "04-03-2026", "quota": "GN", "classType": "2S"
        }
        headers = {"X-RapidAPI-Key": self.api_key, "X-RapidAPI-Host": self.api_host}
        session = await self.get_session()
        request_timeout = aiohttp.ClientTimeout(total=10)
        for ver in ("v3", "v2", "v1"):
            url = f"https://{self.api_host}/api/{ver}/checkSeatAvailability"
            try:
                logger.debug(f"🔍 probing RapidAPI {ver} endpoint")
                async with session.get(url, headers=headers, params=probe_params, timeout=request_timeout) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("status"):
                            SeatVerificationService._detected_version = ver
                            logger.debug(f"🛠 detected working RapidAPI version {ver}")
                            break
                    else:
                        logger.info(f"probe {ver} returned {resp.status}")
            except Exception as e:
                logger.info(f"probe {ver} exception: {e}")
        if not SeatVerificationService._detected_version:
            SeatVerificationService._detected_version = "v1"
            logger.info("defaulting to RapidAPI v1")
        # Optionally persist to redis so other workers know
        try:
            await async_redis_client.set("rapidapi:version", SeatVerificationService._detected_version)
        except Exception:
            pass
        return SeatVerificationService._detected_version

    async def _execute_check_raw_multi(self, train_no, from_code, to_code, date, quota, class_type) -> Optional[Dict]:
        """Perform a single API request using the detected/preferred version.

        This replaces the previous multi‑trial logic which was burning
        quota hitting v3/v2 on every query.
        """
        if not self.api_key:
            return None

        headers = {"X-RapidAPI-Key": self.api_key, "X-RapidAPI-Host": self.api_host}
        params = {
            "trainNo": train_no,
            "fromStationCode": from_code,
            "toStationCode": to_code,
            "date": date,
            "quota": quota,
            "classType": class_type,
        }
        # ensure date is dd-mm-yyyy
        try:
            # if passed a datetime or date object
            if hasattr(date, 'strftime'):
                params['date'] = date.strftime("%d-%m-%Y")
        except Exception:
            pass

        version = await self._detect_working_version()
        url = f"https://{self.api_host}/api/{version}/checkSeatAvailability"
        session = await self.get_session()
        timeout = aiohttp.ClientTimeout(total=60)
        try:
            logger.info(f"📡 RapidAPI {version} request for {train_no}")
            async with session.get(url, headers=headers, params=params, timeout=timeout) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("status"):
                        logger.info(f"✅ RapidAPI {version} success for {train_no}")
                        return data
                    else:
                        logger.warning(f"RapidAPI {version} returned non-OK status for {train_no}: {data}")
                else:
                    logger.warning(f"RapidAPI {version} HTTP {resp.status} for {train_no}: {await resp.text()}")
        except Exception as e:
            logger.error(f"RapidAPI {version} request failed for {train_no}: {e}")
        return None

    async def check_segment(self, train_no: str, from_code: str, to_code: str, date_str: str, quota: str = "GN", class_type: str = "2S") -> Dict[str, Any]:
        """
        Quota-Safe Seat Check:
        1. Redis/Postgres Cache Check (Primary)
        2. Request Coalescing (Prevents duplicate calls for same train/date)
        3. RapidAPI v2 Call -> Caches ALL returned days (usually 6) to save quota.
        """
        await multi_layer_cache.initialize()
        
        try:
            # Normalize date to object for cache keys
            if "-" in date_str and len(date_str.split("-")[0]) == 4:
                travel_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            else:
                # DD-MM-YYYY format
                travel_date = datetime.strptime(date_str, "%d-%m-%Y").date()
        except Exception:
            travel_date = datetime.utcnow().date()

        # simple input validation: train number should be digits
        if not train_no or not train_no.isdigit():
            logger.debug(f"Skipping seat verification, bad train number '{train_no}'")
            return {"available": True, "status": "UNKNOWN", "seats": 0, "fare": 0, "success": False}

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
            logger.info(f"🔥 Quota Saved: Redis Hit for {train_no}")
            return cached

        # 2. Warm Cache (Postgres) - Checked if Redis miss
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
                ttl = self._get_dynamic_ttl(travel_date)
                age = (datetime.utcnow() - db_cache.last_updated_at).total_seconds()
                if age < ttl:
                    res = {
                        "available": "AVAILABLE" in db_cache.status_text.upper() or "AVL" in db_cache.status_text.upper(),
                        "status": db_cache.status_text,
                        "seats": db_cache.seats_available,
                        "fare": db_cache.fare,
                        "last_updated": db_cache.last_updated_at.isoformat(),
                        "success": True
                    }
                    await multi_layer_cache.set_availability(query, res)
                    logger.info(f"✨ Quota Saved: Postgres Hit for {train_no}")
                    return res
        except Exception as e:
            # handle missing column gracefully (migration may be pending)
            err_str = str(e)
            if 'UndefinedColumn' in err_str or 'raw_payload' in err_str:
                logger.warning("Postgres cache missing columns; skipping DB hit (run migration)")
            else:
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
            api_date_str = travel_date.strftime("%d-%m-%Y")
            # negative cache lookup: track invalid train numbers globally (ignores from/to)
            neg_train_key = f"neg_train:{train_no}"
            api_data = None
            try:
                if await async_redis_client.get(neg_train_key):
                    logger.info(f"💤 Negative cache hit for invalid train {train_no}")
                else:
                    api_data = await self._execute_check_raw_multi(train_no, from_code, to_code, api_date_str, quota, class_type)
                    if api_data and api_data.get("status") is False and "valid train number" in str(api_data.get("message", "")).lower():
                        # cache invalid train number for one hour
                        await async_redis_client.setex(neg_train_key, 3600, "1")
                        # suppress downstream logging by returning empty data
                        api_data = None
            except Exception as e:
                logger.warning(f"Negative cache check failed: {e}")
            
            if api_data and api_data.get("status") and api_data.get("data"):
                # PERSIST ALL DAYS RETURNED (Significant quota savings)
                asyncio.create_task(self._persist_bulk_availability(
                    train_no, from_code, to_code, quota, class_type, api_data["data"]
                ))
                
                # Extract specific requested day
                day_data = None
                for item in api_data["data"]:
                    try:
                        item_date = self._parse_api_date(item.get("date"))
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
                    "timestamp": datetime.utcnow().isoformat(),
                    "success": True
                }
            else:
                # If API fails, we don't want to block the user, but we mark it as unverified
                result = {"available": True, "status": "UNKNOWN", "success": False, "error": api_data.get("message") if api_data else "API Timeout"}
            
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

    async def _execute_check_v2_raw(self, train_no, from_code, to_code, date, quota, class_type) -> Optional[Dict]:
        """Uses api/v2 with user's verified parameter format."""
        if not self.api_key: return None
        url = f"{self.base_url_v2}/checkSeatAvailability"
        headers = {"X-RapidAPI-Key": self.api_key, "X-RapidAPI-Host": self.api_host}
        params = {
            "trainNo": train_no, 
            "fromStationCode": from_code, 
            "toStationCode": to_code,
            "date": date, 
            "quota": quota, 
            "classType": class_type
        }
        session = await self.get_session()
        try:
            async with session.get(url, headers=headers, params=params) as resp:
                if resp.status == 200: 
                    return await resp.json()
                else:
                    logger.error(f"RapidAPI v2 Error {resp.status}: {await resp.text()}")
        except Exception as e:
            logger.error(f"RapidAPI v2 Exception: {e}")
        return None

    async def get_train_schedule(self, train_no: str) -> Optional[Dict[str, Any]]:
        """Fetch train schedule from RapidAPI v1 (Confirmed working)."""
        if not self.api_key: return None
        
        # Check cache first (Schedule doesn't change often)
        cache_key = f"schedule:{train_no}"
        try:
            cached = await async_redis_client.get(cache_key)
            if cached: return json.loads(cached)
        except: pass

        url = f"{self.base_url_v1}/getTrainSchedule"
        headers = {"X-RapidAPI-Key": self.api_key, "X-RapidAPI-Host": self.api_host}
        params = {"trainNo": train_no}
        
        session = await self.get_session()
        try:
            async with session.get(url, headers=headers, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("status") and data.get("data"):
                        # Cache schedule for 24 hours to save quota
                        await async_redis_client.setex(cache_key, 86400, json.dumps(data["data"]))
                        return data["data"]
        except Exception as e:
            logger.error(f"Error fetching train schedule: {e}")
        return None

    def _get_dynamic_ttl(self, journey_date) -> int:
        days_left = (journey_date - datetime.utcnow().date()).days
        if days_left > 7: return 21600 # 6 hours
        if days_left > 2: return 7200  # 2 hours
        return 1800 # 30 min

    def _parse_api_date(self, d_str: str) -> date:
        """Parses D-M-YYYY or DD-MM-YYYY."""
        parts = d_str.split("-")
        if len(parts) == 3:
            return date(int(parts[2]), int(parts[1]), int(parts[0]))
        raise ValueError(f"Cannot parse date: {d_str}")

    def _parse_availability_item(self, item: Optional[Dict]) -> bool:
        if not item: return True
        status_text = str(item.get("current_status", "")).upper()
        return any(x in status_text for x in ["AVAILABLE", "AVL", "RAC", "CURR"])

    async def _persist_bulk_availability(self, train_no, from_code, to_code, quota, class_type, data_list):
        """Saves multiple days of availability to Postgres and Redis."""
        from database.session import SessionLocal, engine
        from database.models import TrainAvailabilityCache
        
        if not isinstance(data_list, list): data_list = [data_list]
        
        db = SessionLocal()
        try:
            dialect = engine.dialect.name
            for item in data_list:
                try:
                    j_date = self._parse_api_date(item.get("date"))
                    status = item.get("current_status", "UNKNOWN")
                    
                    if dialect == "postgresql":
                        from sqlalchemy.dialects.postgresql import insert
                        stmt = insert(TrainAvailabilityCache).values(
                            id=str(uuid.uuid4()), train_number=train_no,
                            from_station_code=from_code, to_station_code=to_code,
                            journey_date=j_date, class_type=class_type, quota=quota,
                            status_text=status, seats_available=item.get("seat_avl"),
                            fare=item.get("total_fare"),
                            raw_payload=json.dumps(item),
                            ticket_fare=item.get("ticket_fare"),
                            catering_charge=item.get("catering_charge"),
                            alt_cnf_seat=item.get("alt_cnf_seat"),
                            alt_seat_status=item.get("alt_seat_status"),
                            alt_seat_fare=item.get("alt_seat_fare"),
                            last_updated_at=datetime.utcnow()
                        )
                        on_conflict_stmt = stmt.on_conflict_do_update(
                            constraint='uq_train_availability',
                            set_={
                                "status_text": status,
                                "seats_available": item.get("seat_avl"),
                                "fare": item.get("total_fare"),
                                "raw_payload": json.dumps(item),
                                "ticket_fare": item.get("ticket_fare"),
                                "catering_charge": item.get("catering_charge"),
                                "alt_cnf_seat": item.get("alt_cnf_seat"),
                                "alt_seat_status": item.get("alt_seat_status"),
                                "alt_seat_fare": item.get("alt_seat_fare"),
                                "last_updated_at": datetime.utcnow()
                            }
                        )
                        db.execute(on_conflict_stmt)
                    else:
                        # SQLite fallback for dev
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
                            existing.status_text, existing.seats_available = status, item.get("seat_avl")
                            existing.fare, existing.last_updated_at = item.get("total_fare"), datetime.utcnow()
                            existing.raw_payload = json.dumps(item)
                            existing.ticket_fare = item.get("ticket_fare")
                            existing.catering_charge = item.get("catering_charge")
                            existing.alt_cnf_seat = item.get("alt_cnf_seat")
                            existing.alt_seat_status = item.get("alt_seat_status")
                            existing.alt_seat_fare = item.get("alt_seat_fare")
                        else:
                            db.add(TrainAvailabilityCache(
                                id=str(uuid.uuid4()), train_number=train_no, from_station_code=from_code,
                                to_station_code=to_code, journey_date=j_date, class_type=class_type,
                                quota=quota, status_text=status, seats_available=item.get("seat_avl"),
                                fare=item.get("total_fare"),
                                raw_payload=json.dumps(item),
                                ticket_fare=item.get("ticket_fare"),
                                catering_charge=item.get("catering_charge"),
                                alt_cnf_seat=item.get("alt_cnf_seat"),
                                alt_seat_status=item.get("alt_seat_status"),
                                alt_seat_fare=item.get("alt_seat_fare"),
                                last_updated_at=datetime.utcnow()
                            ))
                    
                    # Also populate Redis for these adjacent days
                    query = AvailabilityQuery(
                        train_id=int(train_no) if train_no.isdigit() else 0,
                        from_stop_id=abs(hash(from_code)) % 1000000,
                        to_stop_id=abs(hash(to_code)) % 1000000,
                        travel_date=j_date, quota_type=quota, class_type=class_type
                    )
                    
                    # Use dynamic TTL to save quota
                    bulk_ttl = self._get_dynamic_ttl(j_date)
                    
                    await multi_layer_cache.set_availability(query, {
                        "available": self._parse_availability_item(item),
                        "status": status, "seats": item.get("seat_avl"),
                        "fare": item.get("total_fare"), "timestamp": datetime.utcnow().isoformat(), "success": True
                    }, ttl=bulk_ttl)
                except: continue
            db.commit()
            logger.info(f"💾 Bulk Persisted {len(data_list)} days for {train_no} (Quota Optimized)")
        except Exception as e:
            logger.error(f"Bulk persistence failure: {e}")
            db.rollback()
        finally:
            db.close()

    async def verify_journey(self, journey: dict) -> bool:
        """Optimized journey verification with parallel lookups."""
        segments = journey.get("legs", journey.get("segments", []))
        tasks = []
        rail_segment_indices = []
        
        for idx, seg in enumerate(segments):
            if seg.get("mode", "").lower() not in ["rail", "train"]: continue
            train_no = seg.get("train_number")
            if not train_no: continue

            rail_segment_indices.append(idx)
            tasks.append(self.check_segment(
                train_no=train_no,
                from_code=seg.get("from_station_code", seg.get("from_station", "")),
                to_code=seg.get("to_station_code", seg.get("to_station", "")),
                date_str=seg.get("departure_time", seg.get("departure", "")).split("T")[0],
                class_type=seg.get("class_type") or "2S" # Default to 2S for quota safety
            ))

        if not tasks: return True
        results = await asyncio.gather(*tasks)
        
        all_available, total_live_cost = True, 0
        for i, res in enumerate(results):
            segment = segments[rail_segment_indices[i]]
            if not res.get("available", True): all_available = False
            
            segment["availability_status"] = res.get("status", "UNKNOWN")
            segment["seats_available"] = res.get("seats", 0)
            
            live_fare = res.get("fare", 0)
            if live_fare > 0:
                segment["fare"] = live_fare
                total_live_cost += live_fare
            else:
                total_live_cost += segment.get("fare", 0)

        if total_live_cost > 0:
            journey["total_cost"] = total_live_cost
            journey["availability_status"] = "AVAILABLE" if all_available else "UNAVAILABLE"

        return all_available
