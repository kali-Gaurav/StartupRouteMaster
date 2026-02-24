"""Re-export of the platform graph mutation API to keep legacy import paths intact."""

from backend.platform.graph import mutation_service as _mutation_service

__all__ = [name for name in dir(_mutation_service) if not name.startswith("_")]

globals().update({name: getattr(_mutation_service, name) for name in __all__})