"""Compatibility entrypoint for running ``uvicorn app.main:app``.

The maintained FastAPI application is defined in :mod:`backend.main`; this
module keeps the short import path working when Uvicorn is launched from the
repository root.
"""

from backend.main import app

__all__ = ["app"]
