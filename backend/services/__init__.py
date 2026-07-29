"""
Services Package (Modularized)
==============================

RouteMaster backend services organized by logical domain.
This module exports the main service interfaces for the application.

Modules:
- planning: Travel planning and reconstruction
- telegram: Bot dispatching and interaction handling
- booking: PNR and reservation services
- finance: Payments and reconciliation
- pricing: Yield and price calculation
- security: Fraud and audit
- cache: Data caching and warming
"""

# Import available services
try:
    from .planning.api import router as travel_planning_router
except (ImportError, ModuleNotFoundError):
    travel_planning_router = None

try:
    from .telegram.bot import telegram_dispatcher
except (ImportError, ModuleNotFoundError):
    telegram_dispatcher = None

__all__ = [
    'travel_planning_router',
    'telegram_dispatcher',
]
