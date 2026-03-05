import hashlib
import array
import logging

logger = logging.getLogger(__name__)

class SOSBloomFilter:
    """
    Task 9: Bloom Filter for Rapid False-Alarm Rejection.
    A probabilistic data structure to filter known malicious phones/payloads.
    """
    def __init__(self, size=100000, hash_count=5):
        self.size = size
        self.hash_count = hash_count
        # 'I' is unsigned int (4 bytes), so size // 32
        self.bit_array = array.array('I', [0] * (size // 32 + 1))

    def _hashes(self, item):
        """Generate multiple hashes for an item."""
        h1 = int(hashlib.md5(str(item).encode()).hexdigest(), 16)
        h2 = int(hashlib.sha1(str(item).encode()).hexdigest(), 16)
        for i in range(self.hash_count):
            yield (h1 + i * h2) % self.size

    def add(self, item):
        for h in self._hashes(item):
            self.bit_array[h // 32] |= (1 << (h % 32))

    def is_blocked(self, item):
        """Check if item is PROBABLY in the blocked list."""
        for h in self._hashes(item):
            if not (self.bit_array[h // 32] & (1 << (h % 32))):
                return False
        return True # Probably blocked

# Global instance for rapid filtering
sos_bloom_filter = SOSBloomFilter()

# Seed with some known malicious mock data
for mock_bad in ["bot-user-1", "+91-0000000000", "test-malicious-payload"]:
    sos_bloom_filter.add(mock_bad)
