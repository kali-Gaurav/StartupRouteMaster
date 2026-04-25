import logging
from typing import Dict, Optional
from services.providers.base_provider import BaseProvider, TransportType
from services.providers.bus_provider import bus_provider
from services.providers.multimodal_mocks import flight_p, taxi_p
from services.providers.rapid_provider import flight_bridge, bus_bridge

logger = logging.getLogger("provider.factory")

class ProviderFactory:
    """
    [G8.1.2] The Multimodal Nexus Factory.
    Registry and dispatcher for all transport adapters.
    """
    _registry: Dict[str, BaseProvider] = {}

    def __init__(self):
        self._registry: Dict[str, BaseProvider] = {}
        # Default registrations
        self.register("bus_provider", bus_provider)
        self.register("flight_p", flight_p)
        self.register("taxi_p", taxi_p)
        # [G11.1] RapidAPI Live Bridges
        self.register("flight_bridge", flight_bridge)
        self.register("bus_bridge", bus_bridge)

    @classmethod
    def register(cls, provider_id: str, provider_instance: BaseProvider):
        """Registers a new adapter into the RouteMaster ecosystem."""
        cls._registry[provider_id] = provider_instance
        logger.info(f"🔌 [PROVIDER_FACTORY] Registered {provider_instance.transport_type.value.upper()} provider: {provider_id}")

    @classmethod
    def get_provider(cls, provider_id: str) -> Optional[BaseProvider]:
        """Retrieves a specific provider adapter."""
        return cls._registry.get(provider_id)

    @classmethod
    def get_providers_by_type(cls, transport_type: TransportType) -> Dict[str, BaseProvider]:
        """Filters providers by transport category."""
        return {k: v for k, v in cls._registry.items() if v.transport_type == transport_type}

    @classmethod
    def get_best_provider(cls, transport_type_str: str) -> Optional[BaseProvider]:
        """Returns the best available provider for a given transport mode."""
        from services.providers.base_provider import TransportType
        try:
            ttype = TransportType(transport_type_str.lower())
            providers = cls.get_providers_by_type(ttype)
            if providers:
                # Naive implementation: return the first one available
                return next(iter(providers.values()))
        except ValueError:
            pass
        return None

# Global singleton for easy access
provider_factory = ProviderFactory()
