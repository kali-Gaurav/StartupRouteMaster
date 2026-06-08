import socket
import struct
import json
import logging
import asyncio
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("udp-safety")

# Task 11: UDP Fallback Protocol
# Packet Format (Binary):
# [10 bytes PNR] [float32 lat] [float32 lng] [uint32 timestamp_offset] = 22 bytes
UDP_IP = "0.0.0.0"
UDP_PORT = 8001

class UDPSafetyListener:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.sock.bind((UDP_IP, UDP_PORT))
            self.sock.setblocking(False)
            logger.info(f"✅ UDP Safety Listener bound to {UDP_IP}:{UDP_PORT}")
        except OSError as e:
            logger.error(f"❌ UDP Safety Listener failed to bind to {UDP_IP}:{UDP_PORT}: {e}")
            logger.warning("Application will continue without UDP safety heartbeats.")
            self.sock = None

    async def start(self):
        if self.sock is None:
            logger.warning("UDP Listener not started (Bind failed).")
            return

        self.running = True
        logger.info(f"🚀 UDP Safety Listener active on port {UDP_PORT}")
        
        loop = asyncio.get_event_loop()
        while self.running:
            try:
                data, addr = await loop.sock_recvfrom(self.sock, 1024)
                if data:
                    print(f"DEBUG: UDP raw data received from {addr}: {data.hex()}")
                
                if len(data) >= 22:
                    pnr_bytes, lat, lng, ts_offset = struct.unpack('10sffi', data[0:22])
                    pnr = pnr_bytes.decode('utf-8', errors='ignore').strip().replace('\x00', '')
                    logger.info(f"📡 [UDP PACKET] Parsed PNR: '{pnr}' at ({lat}, {lng})")
                    asyncio.create_task(self.handle_ping(pnr, lat, lng))
                else:
                    logger.warning(f"⚠️ [UDP] Received undersized packet ({len(data)} bytes) from {addr}")
                    
            except BlockingIOError:
                await asyncio.sleep(0.1) 
            except Exception as e:
                logger.error(f"UDP Loop Error: {e}")
                await asyncio.sleep(0.1)

    async def handle_ping(self, pnr, lat, lng):
        try:
            from api.safety.sos import _redis, PNR_REGISTRY_KEY, _load_event, _save_event
            if _redis:
                eid = _redis.hget(PNR_REGISTRY_KEY, str(pnr))
                if eid:
                    eid = eid.decode('utf-8')
                    event = _load_event(eid)
                    if event:
                        event["lat"] = lat
                        event["lng"] = lng
                        from services.emergency.alert_manager import EmergencyAlertManager
                        mgr = EmergencyAlertManager()
                        enriched = await mgr.process_sos_alert(event)
                        _save_event(enriched)
                        logger.info(f"✅ [UDP SYNC] Updated SOS {eid} via UDP fallback.")
        except Exception as e:
            logger.error(f"Failed to handle UDP ping: {e}")

    def stop(self):
        self.running = False
        if self.sock:
            self.sock.close()

if __name__ == "__main__":
    listener = UDPSafetyListener()
    asyncio.run(listener.start())
