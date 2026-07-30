"""
[Nexus Fix] Bridge for Database Config imports.
This resolves the ModuleNotFoundError across the project by re-exporting 
the Config class from infrastructure.
"""
from .infrastructure.config import Config

__all__ = ["Config"]
