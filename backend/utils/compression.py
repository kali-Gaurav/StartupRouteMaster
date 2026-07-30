import zlib
import json
import logging
from typing import Any, Union, Tuple

logger = logging.getLogger("compression")

class PayloadCompressor:
    """
    Subtask 3.4: Payload Compression Utility.
    Compresses JSON strings using zlib to save Redis memory and bandwidth.
    """
    THRESHOLD_BYTES = 1024 # 1KB threshold

    @staticmethod
    def compress(data: Any) -> Tuple[Union[str, bytes], bool]:
        """
        Compresses data if it exceeds the threshold.
        Returns (payload, was_compressed)
        """
        try:
            json_str = json.dumps(data, default=str)
            raw_bytes = json_str.encode('utf-8')
            
            if len(raw_bytes) < PayloadCompressor.THRESHOLD_BYTES:
                return json_str, False
            
            compressed = zlib.compress(raw_bytes, level=6)
            # logger.debug(f"🗜️ Compressed: {len(raw_bytes)} -> {len(compressed)} bytes")
            return compressed, True
        except Exception as e:
            logger.error(f"Compression error: {e}")
            return json.dumps(data, default=str), False

    @staticmethod
    def decompress(payload: Union[str, bytes]) -> Any:
        """Decompresses payload if it's in bytes (zlib format)."""
        if not payload: return None
        
        try:
            if isinstance(payload, bytes):
                # Attempt zlib decompression
                try:
                    decompressed = zlib.decompress(payload)
                    return json.loads(decompressed.decode('utf-8'))
                except zlib.error:
                    # Not zlib, maybe raw bytes?
                    return json.loads(payload.decode('utf-8'))
            else:
                # Standard string
                return json.loads(payload)
        except Exception as e:
            logger.error(f"Decompression error: {e}")
            return None
