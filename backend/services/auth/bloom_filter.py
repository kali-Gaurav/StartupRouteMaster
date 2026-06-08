import hashlib
import logging
import math
from typing import List

logger = logging.getLogger("user-bloom")

class UserBloomFilter:
    """
    Subtask 1.8: Zero-DB Returning User Tracker.
    Uses a Bloom Filter to instantly check if an IP/Session has been seen before.
    O(1) time complexity, fixed memory footprint.
    """
    def __init__(self, size: int = 100000, hash_count: int = 7):
        self.size = size
        self.hash_count = hash_count
        # Fixed bit array (using bytearray for efficiency)
        self.bit_array = bytearray((size // 8) + 1)
        self.total_seen = 0

    def add(self, user_id: str):
        """Add a user ID (IP/Session) to the filter."""
        for i in range(self.hash_count):
            index = self._get_hash(user_id, i) % self.size
            self.bit_array[index // 8] |= (1 << (index % 8))
        self.total_seen += 1

    def is_returning(self, user_id: str) -> bool:
        """
        Check if user is likely a returning visitor.
        Returns True if 'possibly seen', False if 'definitely not seen'.
        """
        for i in range(self.hash_count):
            index = self._get_hash(user_id, i) % self.size
            if not (self.bit_array[index // 8] & (1 << (index % 8))):
                return False
        return True

    def _get_hash(self, value: str, seed: int) -> int:
        """Fast seeded hash using hashlib."""
        h = hashlib.md5(f"{seed}:{value}".encode()).hexdigest()
        return int(h, 16)

    def get_stats(self):
        # Calculate approximate fill ratio
        bits_set = sum(bin(byte).count('1') for byte in self.bit_array)
        return {
            "size_bits": self.size,
            "bits_set": bits_set,
            "fill_ratio": bits_set / self.size,
            "total_add_ops": self.total_seen
        }

# Global Instance
user_bloom = UserBloomFilter()
