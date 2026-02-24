"""Minimal gRPC client manager stub used for lightweight integration tests."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any


class _RouteLeg(SimpleNamespace):
    pass


class _RouteResult(SimpleNamespace):
    pass


class _RouteClient:
    async def FindRoutes(self, request: Any, **_: Any) -> SimpleNamespace:
        leg = _RouteLeg(
            trip_id=request.from_station_id + "-1",
            from_station_id=request.from_station_id,
            to_station_id=request.to_station_id,
        )
        route = _RouteResult(
            route_id="route_001",
            legs=[leg],
            total_duration_mins=120,
            total_price=250.0,
            reliability_score=0.95,
        )
        return SimpleNamespace(
            search_id="search-1",
            latency_ms=15.75,
            routes=[route],
            total_results=1,
            reliability_score=route.reliability_score,
        )

    async def UpdateGraph(self, request: Any, **_: Any) -> SimpleNamespace:
        return SimpleNamespace(success=True, message=f"Graph updated for {request.train_number}")

    async def GetStationReachability(self, request: Any, **_: Any) -> SimpleNamespace:
        return SimpleNamespace(source_station_id=request.source_station_id, reachable_stations=["1", "2"])


class _InventoryClient(SimpleNamespace):
    async def CheckAvailability(self, request: Any, **_: Any) -> SimpleNamespace:
        return SimpleNamespace(
            train_id=request.train_id,
            total_seats=200,
            available_count=150,
            status="AVAILABLE",
        )

    async def LockSeats(self, request: Any, **_: Any) -> SimpleNamespace:
        return SimpleNamespace(success=True, lock_id="lock_123", expires_in_seconds=request.ttl_seconds)

    async def ReleaseSeats(self, request: Any, **_: Any) -> SimpleNamespace:
        return SimpleNamespace(success=True)

    async def AllocateSeats(self, request: Any, **_: Any) -> SimpleNamespace:
        return SimpleNamespace(
            success=True,
            seat_numbers=["S1", "S2"],
            coach="S1",
            status="ALLOCATED",
            message="Seats allocated",
        )


class _BookingClient(SimpleNamespace):
    async def InitiateBooking(self, request: Any, **_: Any) -> SimpleNamespace:
        return SimpleNamespace(
            success=True,
            pnr="PNR123456789",
            status="CONFIRMED",
            total_amount=request.total_amount,
            payment_status="PAID",
        )

    async def GetBookingStatus(self, request: Any, **_: Any) -> SimpleNamespace:
        return SimpleNamespace(
            status="CONFIRMED",
            payment_status="PAID",
            seat_numbers=["S1"],
        )

    async def CancelBooking(self, request: Any, **_: Any) -> SimpleNamespace:
        return SimpleNamespace(success=True, refund_amount=100.0, cancellation_charge=10.0, message="Cancelled")


class GRPCClientManager:
    """Simplified manager that never hits the network."""

    def __init__(self) -> None:
        self._route_client = _RouteClient()
        self._inventory_client = _InventoryClient()
        self._booking_client = _BookingClient()

    def get_route_client(self, **_: Any) -> _RouteClient:
        return self._route_client

    def get_inventory_client(self, **_: Any) -> _InventoryClient:
        return self._inventory_client

    def get_booking_client(self, **_: Any) -> _BookingClient:
        return self._booking_client


grpc_clients = GRPCClientManager()
__all__ = ["grpc_clients"]