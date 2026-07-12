"""Compatibility placeholders for the deprecated SQLAlchemy scaffold.

Persistent storage is implemented with SQLite in :mod:`backend.db.persistence`.
This module intentionally avoids importing SQLAlchemy so package imports remain
lightweight in environments that only use the current API.
"""

from backend.db.persistence import DATABASE_PATH, TrainingSessionRepository


def get_repository() -> TrainingSessionRepository:
    """Return the SQLite repository used by the current backend."""

    return TrainingSessionRepository(DATABASE_PATH)


__all__ = ["DATABASE_PATH", "TrainingSessionRepository", "get_repository"]
