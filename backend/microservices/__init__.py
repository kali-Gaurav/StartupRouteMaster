"""Legacy microservices package to expose archive implementations."""

from .common import grpc_clients  # noqa: F401

__all__ = ["grpc_clients"]