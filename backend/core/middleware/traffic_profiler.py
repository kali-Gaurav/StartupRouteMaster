import time
import asyncio
import logging
from typing import Dict, Any, Optional, List
from collections import deque
from starlette.types import ASGIApp, Scope, Receive, Send

from core.ml_models.intent_predictor import intent_predictor
from services.shadow_warmer import shadow_warmer
from services.feedback_loop import feedback_loop
from services.user_bloom_filter import user_bloom
from services.behavior_tracker import behavior_tracker
from services.prediction_hub import prediction_hub

logger = logging.getLogger("traffic-profiler")

class TrafficProfile:
    __slots__ = ("timestamp", "method", "path", "headers", "client_ip", "intent", "confidence", "is_returning")
    def __init__(self, scope: Scope):
        self.timestamp = time.time()
        self.method = scope.get("method")
        self.path = scope.get("path")
        raw_headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        self.headers = {
            "user-agent": raw_headers.get("user-agent", ""),
            "x-forwarded-for": raw_headers.get("x-forwarded-for", "")
        }
        self.client_ip = str(scope.get("client", [None])[0])
        self.is_returning = user_bloom.is_returning(self.client_ip)
        user_bloom.add(self.client_ip)
        self.intent = None
        self.confidence = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "path": self.path,
            "headers": self.headers,
            "client_ip": self.client_ip,
            "is_returning": self.is_returning
        }

class AsyncTrafficAnalyzer:
    """
    Standard ASGI Middleware for Telemetry and Prediction Offloading.
    """
    def __init__(self, app: ASGIApp):
        self.app = app
        self.buffer = deque(maxlen=5000)
        self.data_ready = asyncio.Event()
        self.worker_task = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if self.worker_task is None or self.worker_task.done():
            self.worker_task = asyncio.create_task(self._telemetry_worker())

        try:
            profile = TrafficProfile(scope)
            self.buffer.append(profile)
            self.data_ready.set()
            await feedback_loop.record_actual_use(profile.client_ip, profile.path)
        except Exception:
            pass

        await self.app(scope, receive, send)

    async def _telemetry_worker(self):
        while True:
            if not self.buffer:
                self.data_ready.clear()
                await self.data_ready.wait()
            
            while self.buffer:
                profile = self.buffer.popleft()
                try:
                    prediction_hub.push_telemetry(profile.to_dict())
                    if profile.path == "/api/search":
                        await shadow_warmer.warm_by_intent(profile.client_ip, "SEARCH", profile.path)
                except Exception as e:
                    logger.error(f"Offloading error: {e}")
                
                if len(self.buffer) % 100 == 0:
                    await asyncio.sleep(0)
