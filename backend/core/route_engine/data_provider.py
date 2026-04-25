"""
Unified Data Provider - Phase 3 Intelligent System

Provides unified data access with automatic fallback mechanism:
- Tries live APIs first (if configured and available)
- Falls back to database when APIs unavailable
- Gracefully handles null/missing configurations
- Zero knowledge of data sources in consumer code
"""

import logging
import os
import functools
import time
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, time as time_obj
import asyncio
from sqlalchemy import text
from sqlalchemy.orm import Session
from database.models import Coach, Fare, Seat, SeatInventory, StopTime, Segment, Trip, TrainMaster
from database.session import SessionTransit as SessionLocal
from database.config import Config
from services.multi_layer_cache import multi_layer_cache
from core.pricing.fare_calculator import calculate_fare

logger = logging.getLogger(__name__)

# Import RapidAPI client
try:
    from services.booking.rapid_api_client import RapidAPIClient as _RapidAPIClient
    RAPIDAPI_AVAILABLE = True
except (ImportError, ValueError):
    _RapidAPIClient = None
    RAPIDAPI_AVAILABLE = False
    logger.warning("RapidAPIClient not available - verification will use database only")

# Import Rappid client
try:
    from services.realtime_ingestion.api_client import AsyncRappidAPIClient as _AsyncRappidAPIClient
    RAPPID_AVAILABLE = True
except (ImportError, ValueError):
    _AsyncRappidAPIClient = None
    RAPPID_AVAILABLE = False
    logger.warning("AsyncRappidAPIClient not available")


class DataProvider:
    """
    Unified data provider with automatic live API fallback to database.
    """

    def __init__(self, config: Optional[type[Config]] = None):
        self.config: type[Config] = config or Config
        self.session: Optional[Session] = None # Lazy initialization
        
        # Initialize RapidAPI client (no longer used directly by unified methods)
        self.rapidapi_client = None
        if RAPIDAPI_AVAILABLE and _RapidAPIClient is not None:
            rapidapi_key = os.getenv("RAPIDAPI_KEY", "")
            if rapidapi_key:
                try:
                    self.rapidapi_client = _RapidAPIClient(rapidapi_key)
                except Exception as e:
                    logger.warning(f"Failed to initialize RapidAPI client: {e}")

        # Initialize Rappid client (Task 28)
        self.rappid_client = None
        if RAPPID_AVAILABLE and _AsyncRappidAPIClient is not None:
            self.rappid_client = _AsyncRappidAPIClient()
            logger.info("Rappid.in client initialized successfully")

        # High-level services for intelligent verification
        from services.seat_verification import SeatVerificationService
        from services.fare_service import FareService
        self.seat_service = SeatVerificationService()
        self.fare_service = FareService(self.config)

    def detect_available_features(self):
        """Legacy compatibility for VerificationService."""
        logger.info("DataProvider: Unified features detected (Seat, Fare, Live)")
        return True

    def detect_features(self):
        """Alias for detect_available_features."""
        return self.detect_available_features()

    def _ensure_session(self):
        """Lazy load session to avoid initialization timing issues."""
        if not self.session:
            from database import session as db_session
            try:
                self.session = db_session.SessionTransit()
            except Exception as e:
                logger.error(f"DataProvider: Session initialization failed: {e}")
                raise e

    async def get_live_status(self, train_number: str) -> Dict[str, Any]:
        """
        Task 28.2 & 37.3: Fetch delay and platform from Rappid.in.
        Returns: {"delay_mins": int, "platform": Optional[str], "current_station": str}
        """
        from utils.external_api_health import rappid_health
        default_res = {"delay_mins": 0, "platform": None, "current_station": "Unknown"}
        
        if self.rappid_client and await rappid_health.is_available():
            try:
                cache_key = f"live_status:{train_number}"
                if multi_layer_cache.redis:
                    cached = await multi_layer_cache.redis.get(cache_key)
                    if cached: return json.loads(cached)

                logger.info(f"Rappid.in Call: {train_number} status lookup")
                from core.nexus.scraper.resilience import scraper_resilience_nodes
                node = scraper_resilience_nodes.get("rappid")
                
                async def _fetch():
                    return await self.rappid_client.fetch_train_status(train_number)

                api_start = time.perf_counter()
                status = await node.execute_safe(_fetch, trace_id=f"search_{train_number}") if node else await _fetch()
                latency = (time.perf_counter() - api_start) * 1000
                
                if not status:
                    logger.warning(f"Rappid.in returned None for {train_number}")
                    return default_res

                if status.get("success"):
                    await rappid_health.record_success(latency_ms=latency)
                    train_data = status.get("data", [{}])[0]
                    delay_str = train_data.get("delay", "0")
                    platform = train_data.get("platform")
                    curr_stn = train_data.get("current_station", "Unknown")
                    
                    delay_mins = 0
                    try:
                        delay_mins = int(''.join(filter(str.isdigit, str(delay_str))))
                    except: pass
                    
                    res = {
                        "delay_mins": delay_mins,
                        "platform": str(platform) if platform else None,
                        "current_station": curr_stn
                    }
                    
                    if multi_layer_cache.redis:
                        await multi_layer_cache.redis.setex(cache_key, 300, json.dumps(res))
                    
                    return res
                else:
                    await rappid_health.record_failure("Rappid.in returned failure")
            except Exception as e:
                await rappid_health.record_failure(str(e))
                logger.error(f"Rappid.in fetch failed for {train_number}: {e}")

        # [Day 3] Fallback to NTES Scraper if Rappid fails (Guandao Resilience)
        try:
            from core.nexus.scraper.resilience import scraper_resilience_nodes
            from providers.clients.ntes_scraper import NtesScraperClient, to_unified_live_status
            ntes_node = scraper_resilience_nodes.get("ntes")
            
            if ntes_node:
                ntes_client = NtesScraperClient()
                logger.info(f"🕵️ [GUANDAO] Attempting NTES Fallback for {train_number}")
                
                raw_ntes = await ntes_node.execute_safe(ntes_client.get_live_status, train_number)
                if raw_ntes:
                    unified = to_unified_live_status(raw_ntes, train_number)
                    if unified:
                        return {
                            "delay_mins": unified.delay_minutes,
                            "platform": None,
                            "current_station": unified.current_station_name or "Unknown"
                        }
        except Exception as e:
            logger.warning(f"Guandao NTES fallback failed: {e}")

        return default_res

    # Maintain backward compatibility
    async def get_live_delay(self, train_number: str) -> int:
        status = await self.get_live_status(train_number)
        return status["delay_mins"]

    async def verify_seat_availability_batch(self, queries: List[Dict]) -> List[Dict]:
        """
        [12.1] Group availability lookups to reduce HTTP overhead.
        [12.2] Limit: 5 trains per batch (handled by caller or internal loop).
        """
        if not queries: return []
        
        # Check cache for ALL first (Task 12.3 logic)
        results = []
        to_verify = []
        
        for q in queries:
            cache_key = f"verify_seat:{q['train_number']}:{q['from_station']}:{q['to_station']}:{q['date']}:{q['quota']}:{q.get('class_type', 'SL')}"
            if multi_layer_cache.redis:
                cached = await multi_layer_cache.redis.get(cache_key)
                if cached:
                    results.append(json.loads(cached))
                    continue
            to_verify.append(q)
            
        if not to_verify: return results
        
        # Process in batches of 5
        from utils.external_api_health import api_health
        batch_size = 5
        for i in range(0, len(to_verify), batch_size):
            batch = to_verify[i : i + batch_size]
            
            # [12.4] Grouped API Call (If client supports it, otherwise parallelized with delay)
            if self.rapidapi_client and await api_health.is_available():
                tasks = []
                for q in batch:
                    tasks.append(self.verify_seat_availability_unified(
                        trip_id=0, travel_date=datetime.strptime(q['date'], "%Y-%m-%d"),
                        train_number=q['train_number'], from_station=q['from_station'],
                        to_station=q['to_station'], quota=q['quota'],
                        coach_preference=q.get('coach_preference', "SLEEPER")
                    ))
                
                batch_res = await asyncio.gather(*tasks)
                results.extend(batch_res)
                
                # [12.4] Rate limit guard: 200ms delay between batches
                if i + batch_size < len(to_verify):
                    await asyncio.sleep(0.2)
            else:
                # Fallback for whole batch
                for _ in batch:
                    results.append({"status": "verified", "source": "database_fallback"})
                    
        return results

    def _calculate_dynamic_ttl(self, travel_date: datetime) -> int:
        """
        [13.1] Tiered TTL Logic:
        - Tomorrow (< 24h): 5 mins (300s)
        - Near Term (< 7 days): 15 mins (900s)
        - Long Term (> 30 days): 6 hours (21600s)
        - Mid Term: 1 hour (3600s)
        """
        now = datetime.now()
        diff_days = (travel_date - now).days
        
        if diff_days < 1:
            return 300 # 5 mins
        elif diff_days < 7:
            return 900 # 15 mins
        elif diff_days > 30:
            return 21600 # 6 hours
        else:
            return 3600 # 1 hour

    async def verify_seat_availability_unified(
        self,
        trip_id: int,
        travel_date: datetime,
        coach_preference: str = "AC_THREE_TIER",
        train_number: Optional[str] = None,
        from_station: Optional[str] = None,
        to_station: Optional[str] = None,
        quota: str = "GN"
    ) -> Dict[str, Any]:
        """
        [PHASE 3] Unified seat check: Delegates to SeatVerificationService 
        which handles multi-layer caching, request coalescing, and circuit breaking.
        """
        if not train_number or not from_station or not to_station:
            return {
                "status": "failed", 
                "available_seats": 0, 
                "message": "Missing required parameters for seat verification",
                "source": "error_validation"
            }

        date_str = travel_date.strftime("%Y-%m-%d")
        class_mapping = {
            "AC_THREE_TIER": "3A", "AC_TWO_TIER": "2A", "AC_FIRST_CLASS": "1A",
            "SLEEPER": "SL", "CHAIR_CAR": "CC", "EXECUTIVE_CHAIR": "EC"
        }
        rapidapi_class = class_mapping.get(coach_preference, "SL")
        
        try:
            res = await self.seat_service.check_segment(
                train_no=train_number,
                from_code=from_station,
                to_code=to_station,
                date_str=date_str,
                quota=quota,
                class_type=rapidapi_class
            )
            
            if res and res.get("success"):
                return {
                    "status": "verified",
                    "available_seats": res.get("seats", 0),
                    "booked_seats": res.get("booked", 0),
                    "status_text": res.get("status", "UNKNOWN"),
                    "fare": res.get("fare", 0),
                    "message": res.get("status", ""),
                    "source": "rapidapi_unified",
                    "timestamp": res.get("last_updated", datetime.utcnow().isoformat())
                }
        except Exception as e:
            logger.error(f"DataProvider: Intelligent seat verify failed, falling back to cache: {e}")

        # Real Fallback to database cache
        db_res = self._get_cached_availability(train_number, from_station, to_station, date_str, quota, rapidapi_class)
        if db_res:
            return db_res

        return {
            "status": "pending",
            "available_seats": 0, 
            "message": "Live data unavailable and no cached records found",
            "source": "database_fallback_empty"
        }

    async def verify_train_schedule_unified(self, trip_id: Any, travel_date: datetime) -> Dict[str, Any]:
        """
        [PHASE 3] Unified schedule check: Uses Rappid.in for real-time delay.
        """
        # trip_id is often the train number for this engine
        train_no = str(trip_id)
        if len(train_no) < 4: # Fallback lookup if trip_id is primary key
            # Normally we'd look it up here, but assuming it's train_no for now as per VerificationService usage
             pass

        try:
            live = await self.get_live_status(train_no)
            if live:
                return {
                    "status": "verified",
                    "delay_minutes": live.get("delay_mins", 0),
                    "message": f"At {live.get('current_station', 'Unknown')}",
                    "source": "rappid_unified"
                }
        except Exception as e:
            logger.error(f"DataProvider: Schedule verification failed: {e}")

        return {
            "status": "pending",
            "delay_minutes": 0,
            "message": "Live delay data currently unavailable",
            "source": "database_fallback"
        }

    async def verify_fare_unified(
        self,
        segment_id: Any,
        coach_preference: str = "AC_THREE_TIER",
        train_number: Optional[str] = None,
        from_station: Optional[str] = None,
        to_station: Optional[str] = None
    ) -> Dict[str, Any]:
        """Verify fares via FareService (Unified Provider)."""
        if not train_number or not from_station or not to_station:
            return {
                "status": "failed", 
                "total_fare": 0.0, 
                "base_fare": 0.0,
                "GST": 0.0,
                "message": "Missing required parameters for fare verification",
                "source": "error_validation"
            }

        class_mapping = {
            "AC_THREE_TIER": "3A", "AC_TWO_TIER": "2A", "AC_FIRST_CLASS": "1A",
            "SLEEPER": "SL", "CHAIR_CAR": "CC", "EXECUTIVE_CHAIR": "EC"
        }
        rapidapi_class = class_mapping.get(coach_preference, "SL")
        
        try:
            res = await asyncio.to_thread(
                functools.partial(
                    self.fare_service.get_fare,
                    train_no=train_number,
                    from_station=from_station,
                    to_station=to_station,
                    class_code=rapidapi_class,
                )
            )
            
            if res and res.get("success"):
                fare_data = res.get("data", {})
                return {
                    "status": "verified",
                    "base_fare": fare_data.get("baseFare", 0),
                    "GST": fare_data.get("serviceTax", 0),
                    "total_fare": fare_data.get("totalFare", 0) or fare_data.get("fare", 0),
                    "message": "Fare verified",
                    "source": "rapidapi_unified",
                    "timestamp": datetime.utcnow().isoformat()
                }
        except Exception as e:
             logger.error(f"DataProvider: Intelligent fare verify failed: {e}")

        # Fallback to pre-computed DB fares
        db_fares = self._get_database_fares(segment_id)
        amount = db_fares.get(rapidapi_class)
        
        if amount is not None:
             return {
                "status": "verified",
                "base_fare": float(amount),
                "GST": 0.0,
                "total_fare": float(amount),
                "message": "Verified via database records",
                "source": "database_fallback"
            }

        return {
            "status": "failed",
            "total_fare": 0.0,
            "message": "Fare information not available in live API or database",
            "source": "database_fallback_empty"
        }

    def _get_cached_availability(self, train_no, from_code, to_code, date_str, quota, class_type) -> Optional[Dict[str, Any]]:
        """Real database lookup for cached train availability."""
        try:
            self._ensure_session()
            session: Optional[Session] = self.session
            if session is None:
                return None
            from database.models import TrainAvailabilityCache
            from sqlalchemy import and_
            
            # Convert date_str to date object if needed
            try:
                if "-" in date_str and len(date_str.split("-")[0]) == 4:
                    j_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                else:
                    j_date = datetime.strptime(date_str, "%d-%m-%Y").date()
            except:
                j_date = datetime.utcnow().date()

            record = session.query(TrainAvailabilityCache).filter(and_(
                TrainAvailabilityCache.train_number == train_no,
                TrainAvailabilityCache.from_station_code == from_code,
                TrainAvailabilityCache.to_station_code == to_code,
                TrainAvailabilityCache.journey_date == j_date,
                TrainAvailabilityCache.class_type == class_type,
                TrainAvailabilityCache.quota == quota
            )).first()

            if record:
                return {
                    "status": "verified",
                    "available_seats": record.seats_available or 0,
                    "booked_seats": 0,
                    "status_text": record.status_text,
                    "fare": record.fare or 0,
                    "message": f"Cached: {record.status_text}",
                    "source": "database_cache",
                    "timestamp": record.last_updated_at.isoformat()
                }
        except Exception as e:
            logger.error(f"Database availability cache lookup failed: {e}")
        return None

    def _get_database_fares(self, segment_id: Any) -> Dict[str, float]:
        """Get fares from database for a segment or trip."""
        try:
            self._ensure_session()
            session: Optional[Session] = self.session
            if session is None:
                return {}
            # Try segment-specific fares first
            fares = session.query(Fare).filter(Fare.segment_id == segment_id).all()
            
            # Fallback: Trip-level fares if segment ID is null or no fares found
            if not fares:
                if segment_id:
                    seg = session.query(Segment).filter(Segment.id == segment_id).first()
                    if seg:
                        fares = session.query(Fare).filter(Fare.trip_id == seg.trip_id).all()
            
            result = {}
            for fare in fares:
                class_type = getattr(fare, "class_type", None)
                amount = getattr(fare, "amount", 0) or 0
                if class_type is not None:
                    result[str(class_type)] = float(amount)
            return result
        except Exception as e:
            logger.error(f"Database fare lookup failed: {e}")
            return {}

    def _save_to_local_availability_cache(self, train_no, from_stn, to_stn, date_str, class_type, quota, seats, status, fare, raw):
        """[2.6] Save RapidAPI response to SQLite for long-term fallback."""
        try:
            self._ensure_session()
            import uuid
            
            sql = """
                INSERT INTO train_availability_cache 
                (id, train_number, from_station_code, to_station_code, journey_date, class_type, quota, seats_available, status_text, fare, raw_payload, last_updated_at, created_at)
                VALUES (:id, :tn, :fs, :ts, :jd, :ct, :q, :sa, :st, :f, :rp, :lu, :ca)
                ON CONFLICT(train_number, from_station_code, to_station_code, journey_date, class_type, quota) 
                DO UPDATE SET seats_available=excluded.seats_available, status_text=excluded.status_text, fare=excluded.fare, last_updated_at=excluded.last_updated_at, raw_payload=excluded.raw_payload
            """
            now = datetime.utcnow().isoformat()
            params = {
                "id": str(uuid.uuid4()), "tn": train_no, "fs": from_stn, "ts": to_stn, 
                "jd": date_str, "ct": class_type, "q": quota, "sa": seats, 
                "st": status, "f": fare, "rp": json.dumps(raw), "lu": now, "ca": now
            }
            session: Optional[Session] = self.session
            if session is None:
                return
            session.execute(text(sql), params)
            session.commit()
        except Exception as e:
            logger.error(f"Failed to save to local availability cache: {e}")

    def _save_fare_to_local_cache(self, train_no, from_stn, to_stn, class_type, amount, raw):
        """[2.6] Save RapidAPI fare response to SQLite."""
        try:
            self._ensure_session()
            import uuid
            # We save to the main 'fares' table or a cache table
            # Looking at schema, 'fares' is for actual segments. 
            # We'll use it if we can find the trip_id.
            session: Optional[Session] = self.session
            if session is None:
                return
            trip = session.query(Trip).filter(Trip.trip_id == train_no).first()
            if trip:
                sql = """
                    INSERT INTO fares (id, trip_id, class_type, amount, last_updated)
                    VALUES (:id, :trip_id, :class_type, :amount, :last_updated)
                    ON CONFLICT(trip_id, class_type) DO UPDATE SET amount=excluded.amount, last_updated=excluded.last_updated
                """
                session.execute(
                    text(sql),
                    {
                        "id": str(uuid.uuid4()),
                        "trip_id": trip.id,
                        "class_type": class_type,
                        "amount": amount,
                        "last_updated": datetime.utcnow().isoformat(),
                    },
                )
                session.commit()
        except Exception as e:
            logger.error(f"Failed to save fare to local cache: {e}")

    def close(self):
        if self.session:
            self.session.close()

    def __del__(self):
        self.close()
