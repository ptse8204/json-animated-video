"""Local SaaS backend foundation for MotionJSON.

The backend is intentionally framework-independent. It uses SQLite for
metadata and a StorageProvider for bytes so HTTP/API layers can be added later
without changing project, job, asset, or usage behavior.
"""

from .db import connect, initialize_database

__all__ = ["connect", "initialize_database"]
