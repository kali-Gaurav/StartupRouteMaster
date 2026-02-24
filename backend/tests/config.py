"""Minimal config used specifically by the tests package."""

import os
from backend.config import Config as BaseConfig


class Config(BaseConfig):
    TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")

    @classmethod
    def get_test_engine_url(cls) -> str:
        return cls.TEST_DATABASE_URL


__all__ = ["Config"]