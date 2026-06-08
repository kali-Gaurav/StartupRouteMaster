from fastapi import APIRouter

router = APIRouter()

for module_name in [
    "admin", "admin_auth", "admin_commissions", "admin_fraud", "agent", "agents",
    "booking", "booking_ws", "credits", "debug", "external_api", "finance_v2", "karma",
    "live", "monitoring", "notifications", "realtime", "search", "sessions",
    "unlock", "user", "webhooks",
]:
    try:
        module = __import__(f"{__name__}.{module_name}", fromlist=["router"])
        router.include_router(module.router)
    except ImportError:
        pass
