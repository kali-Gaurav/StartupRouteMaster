import zlib
import json
import logging

logger = logging.getLogger("compression")

class JSONCompression:
    @staticmethod
    def compress(data: dict) -> bytes:
        """Compress dict to binary blob using max zlib level."""
        try:
            json_str = json.dumps(data, default=str)
            return zlib.compress(json_str.encode('utf-8'), level=9)
        except Exception as e:
            logger.error(f"Compression failed: {e}")
            return b""

    @staticmethod
    def decompress(blob: bytes) -> dict:
        """Decompress binary blob back to dict."""
        if not blob: return {}
        try:
            json_str = zlib.decompress(blob).decode('utf-8')
            return json.loads(json_str)
        except Exception as e:
            logger.error(f"Decompression failed: {e}")
            return {}
