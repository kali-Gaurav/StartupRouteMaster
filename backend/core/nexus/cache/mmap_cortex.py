import mmap
import os
import logging
import time
from typing import Optional
from database.config import Config

logger = logging.getLogger("nexus.cache.cortex")

# Constants for the Mmap Spine
CORTEX_FILE = "nexus_vitals.mmap"
CORTEX_SIZE = 64 * 1024 # 64 KB Shared Region

# Bit Offsets for Byte 0 (Global Status)
BIT_MASTER_KILL = 0
BIT_MAINTENANCE = 1
BIT_FINANCIAL_PANIC = 2
BIT_SCAPER_THROTTLE = 3
BIT_SAFE_MODE = 4

class NexusMmapCortex:
    """
    [Task 41] The Neural Spine of the Nexus Fiber.
    A Zero-Latency Shared Memory region for inter-process state.
    Bypasses Redis networking for "Hot-Path" Gatekeeper checks.
    """
    
    def __init__(self, path: Optional[str] = None):
        if not path:
            os.makedirs(Config.MEMMAP_DIR, exist_ok=True)
            self.path = os.path.join(Config.MEMMAP_DIR, CORTEX_FILE)
        else:
            self.path = path
            
        self._mm: Optional[mmap.mmap] = None
        self._ensure_file_exists()
        self._map_file()
        assert self._mm is not None, "Cortex failed to initialize mmap"

    def _ensure_file_exists(self):
        """Prepare the shared memory backing file with zero-padding."""
        if not os.path.exists(self.path):
            with open(self.path, "wb") as f:
                f.write(b'\x00' * CORTEX_SIZE)
            logger.warning(f"🛡️ [CORTEX] Initialized fresh shared spine: {CORTEX_FILE}")

    def _map_file(self):
        """Memory-map the backing file into the current process space."""
        try:
            f = open(self.path, "r+b")
            # Share as writeable, but use SWMR pattern (Single Writer, Multi-Reader)
            self._mm = mmap.mmap(f.fileno(), CORTEX_SIZE, access=mmap.ACCESS_WRITE)
            logger.info("🛡️ [CORTEX] Successfully mapped Nexus Neural Spine (L0).")
        except Exception as e:
            logger.critical(f"🛑 [CORTEX] FAILED TO MAP SHARED SPINE: {e}")
            raise

    @property
    def mm(self) -> mmap.mmap:
        """Get the mmap object, ensuring it's initialized."""
        if self._mm is None:
            raise RuntimeError("Nexus Cortex not properly initialized")
        return self._mm

    # --------------------------------------------------------------------------
    # CORE ACCESSORS (Fast-Path)
    # --------------------------------------------------------------------------
    
    def get_byte(self, offset: int) -> int:
        """Returns the raw byte at the specified offset."""
        return self.mm[offset]

    def set_byte(self, offset: int, value: int):
        """Sets the raw byte at the specified offset (Single-Writer Only)."""
        self.mm[offset] = value

    def get_bit(self, byte_offset: int, bit_offset: int) -> bool:
        """Check a specific bit status (Efficiency: < 10ns)."""
        byte_val = self.mm[byte_offset]
        return bool(byte_val & (1 << bit_offset))

    def set_bit(self, byte_offset: int, bit_offset: int, status: bool):
        """Set or Clear a bit (Must be called by a designated Master/Node)."""
        current = self.mm[byte_offset]
        if status:
            new_val = current | (1 << bit_offset)
        else:
            new_val = current & ~(1 << bit_offset)
        self.mm[byte_offset] = new_val

    def get_stress_index(self) -> int:
        """Returns the SSI (0-100) from Byte 1."""
        return self.mm[1]

    def set_stress_index(self, value: int):
        """Sets the SSI (0-100) at Byte 1."""
        self.mm[1] = min(100, max(0, value))

    def get_cpu_percent(self) -> int:
        return self.mm[2]

    def set_cpu_percent(self, value: int):
        self.mm[2] = min(100, max(0, int(value)))

    def get_ram_percent(self) -> int:
        return self.mm[3]

    def set_ram_percent(self, value: int):
        self.mm[3] = min(100, max(0, int(value)))

    def get_io_wait(self) -> int:
        return self.mm[4]

    def set_io_wait(self, value: int):
        self.mm[4] = min(100, max(0, int(value)))

    def get_redis_percent(self) -> int:
        return self.mm[5]

    def set_redis_percent(self, value: int):
        self.mm[5] = min(100, max(0, int(value)))

    # [Task 43] Search Deduplication bitset (1024 bytes = 8192 bits)
    IN_FLIGHT_OFFSET = 1000 
    
    def mark_in_flight(self, hash_idx: int, status: bool):
        """Toggle a bit in the 8192-bit search signature matrix."""
        byte_off = self.IN_FLIGHT_OFFSET + (hash_idx // 8)
        bit_off = hash_idx % 8
        
        current = self.mm[byte_off]
        if status:
            new_val = current | (1 << bit_off)
        else:
            new_val = current & ~(1 << bit_off)
        self.mm[byte_off] = new_val

    def is_in_flight(self, hash_idx: int) -> bool:
        """Check if an identical search is ALREADY being processed by another worker."""
        byte_off = self.IN_FLIGHT_OFFSET + (hash_idx // 8)
        bit_off = hash_idx % 8
        return bool(self.mm[byte_off] & (1 << bit_off))

    # [Task 44] Zero-Copy Hot Slabs (32KB allocated for top results)
    HOT_SLABS_OFFSET = 4096 
    SLAB_SIZE = 1024 # 1KB per slab
    MAX_SLABS = 32

    def store_slab(self, slab_idx: int, data: bytes):
        """Store raw bytes into a designated slab (Max 1KB)."""
        idx = min(self.MAX_SLABS - 1, slab_idx)
        start = self.HOT_SLABS_OFFSET + (idx * self.SLAB_SIZE)
        # Pad or truncate to SLAB_SIZE
        padded_data = data[:self.SLAB_SIZE].ljust(self.SLAB_SIZE, b'\x00')
        self.mm[start:start+self.SLAB_SIZE] = padded_data

    def get_slab(self, slab_idx: int) -> bytes:
        """Retrieve raw bytes from a designated slab (Fast-Path)."""
        idx = min(self.MAX_SLABS - 1, slab_idx)
        start = self.HOT_SLABS_OFFSET + (idx * self.SLAB_SIZE)
        return self.mm[start:start+self.SLAB_SIZE].rstrip(b'\x00')

    # [Task 45] Atomic Zombie Watchdog (Heartbeats for 128 workers)
    HEARTBEAT_OFFSET = 8000 
    
    def write_heartbeat(self, worker_id: int):
        """Worker checks-in at L0 layer."""
        idx = min(127, worker_id)
        start = self.HEARTBEAT_OFFSET + (idx * 4)
        ts_bytes = int(time.time() % 10**8).to_bytes(4, byteorder='big')
        self.mm[start:start+4] = ts_bytes

    def get_heartbeat(self, worker_id: int) -> int:
        """Watchdog checks if worker is alive."""
        idx = min(127, worker_id)
        start = self.HEARTBEAT_OFFSET + (idx * 4)
        return int.from_bytes(self.mm[start:start+4], byteorder='big')

    # [Task 46] Scraper Session Global Warming (Shared session cookies)
    SESSION_POOL_OFFSET = 9000 
    SESSION_SLOT_SIZE = 128
    
    def write_session(self, slot_idx: int, session_data: str):
        """Worker stores a warm IRCTC session cookie."""
        idx = min(9, slot_idx)
        start = self.SESSION_POOL_OFFSET + (idx * self.SESSION_SLOT_SIZE)
        encoded = session_data.encode().ljust(self.SESSION_SLOT_SIZE, b'\x00')
        self.mm[start:start+self.SESSION_SLOT_SIZE] = encoded

    def get_session(self, slot_idx: int) -> Optional[str]:
        """Worker retrieves a warm IRCTC session cookie."""
        idx = min(9, slot_idx)
        start = self.SESSION_POOL_OFFSET + (idx * self.SESSION_SLOT_SIZE)
        raw = self.mm[start:start+self.SESSION_SLOT_SIZE].rstrip(b'\x00')
        return raw.decode() if raw else None

    # --------------------------------------------------------------------------
    # HIGH-LEVEL VITALS (Task 41.2)
    # --------------------------------------------------------------------------

    def is_panic(self) -> bool:
        """Instant check for Global Financial Panic (Byte 0, Bit 2)."""
        return self.get_bit(0, BIT_FINANCIAL_PANIC)

    def is_kill_switch_active(self) -> bool:
        """Instant check for Master Kill (Byte 0, Bit 0)."""
        return self.get_bit(0, BIT_MASTER_KILL)

    def set_panic(self, state: bool):
        """Trigger or Clear Global Financial Panic."""
        self.set_bit(0, BIT_FINANCIAL_PANIC, state)
        if state: logger.critical("🚨 [CORTEX] GLOBAL FINANCIAL PANIC ENGAGED!")

    def set_master_kill(self, state: bool):
        """Trigger or Clear Master Halt Switch."""
        self.set_bit(0, BIT_MASTER_KILL, state)
        if state: logger.critical("🛑 [CORTEX] MASTER KILL SWITCH ENGAGED!")

    def set_vitals(self, is_panic: Optional[bool] = None, is_kill: Optional[bool] = None, is_throttle: Optional[bool] = None):
        """Used by the Sentinel Node to update global state."""
        if is_panic is not None: self.set_bit(0, BIT_FINANCIAL_PANIC, is_panic)
        if is_kill is not None: self.set_bit(0, BIT_MASTER_KILL, is_kill)
        if is_throttle is not None: self.set_bit(0, BIT_SCAPER_THROTTLE, is_throttle)

    def close(self):
        if self._mm:
            self._mm.close()

# Global Singleton for the Process
nexus_cortex = NexusMmapCortex()
