from fastapi import APIRouter

router = APIRouter()

for module_name in [
    "bookings", "governor", "model_search", "nexus_dashboard",
    "scraper_controller", "search", "sos", "system", "transit", "guardian",
    "swarm"
]:
    module = __import__(f"{__name__}.{module_name}", fromlist=["router"])
    router.include_router(module.router)
