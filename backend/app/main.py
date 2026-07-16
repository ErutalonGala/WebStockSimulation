"""Compatibility entrypoint for deployments that import ``backend.app.main``.

The actively maintained API lives in :mod:`backend.main`.  Re-exporting the same
FastAPI app here keeps older README commands and ASGI configurations working
without requiring the removed SQLAlchemy scaffold.

This module is also imported as ``app.main`` when Uvicorn is launched from the
``backend`` directory.  In that layout, Python only adds ``backend`` itself to
``sys.path``, so the repository root must be added before importing the
``backend`` package.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from backend.main import app

__all__ = ["app"]
