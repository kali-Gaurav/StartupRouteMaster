import logging
from fastapi import APIRouter, Request, HTTPException, Depends
from core.nexus.security.firewall import nexus_firewall

logger = logging.getLogger("nexus.api.admin_security")

router = APIRouter(prefix="/admin/security", tags=["AdminSecurity"])

@router.post("/knock")
async def knock_gate(request: Request, key: str):
    """
    [Task 2.6] Dynamic SSH Unlock (Port Knocking).
    If the key matches, the client's public IP is allowed on Port 22.
    """
    client_ip = request.client.host
    
    # 1. Verify Knock Key (High intensity admin key)
    from database.config import Config
    if key != Config.NEXUS_ADMIN_KEY: # This must be set in ENV
         logger.warning(f"🚨 [GATE] Unauthorized Knock Attempt from {client_ip}!")
         raise HTTPException(status_code=403, detail="INVALID_KNOCK_KEY")

    # 2. Add IP to Firewall for SSH
    # ufw allow from <IP> to any port 22
    cmd = ["ufw", "allow", "from", client_ip, "to", "any", "port", "22", "proto", "tcp"]
    result = nexus_firewall._run_cmd(cmd)
    
    logger.info(f"✨ [GATE] SSH Port 22 unlocked for administrative IP: {client_ip}")
    return {"status": "UNLOCKED", "ip": client_ip, "detail": result}

@router.get("/status")
async def firewall_status():
    """Administrative status view of the OS Firewall."""
    status = await nexus_firewall.get_status()
    return {"status": "SUCCESS", "ufw_output": status}
