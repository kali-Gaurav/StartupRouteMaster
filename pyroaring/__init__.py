"""Lightweight PyRoaring-compatible shim used during local testing."""

import pickle
from typing import Iterable


class BitMap:
    def __init__(self, iterable: Iterable[int] | None = None):
        self._set = set(iterable or [])

    def __ior__(self, other):
        if isinstance(other, BitMap):
            self._set |= other._set
        else:
            self._set |= set(other)
        return self

    def __or__(self, other):
        if isinstance(other, BitMap):
            data = self._set | other._set
        else:
            data = self._set | set(other)
        return BitMap(data)

    def __iter__(self):
        return iter(self._set)

    def serialize(self) -> bytes:
        return pickle.dumps(sorted(self._set))

    @classmethod
    def deserialize(cls, blob: bytes) -> "BitMap":
        try:
            data = pickle.loads(blob)
        except Exception:
            data = []
        return BitMap(data)