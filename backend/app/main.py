"""Compatibility entrypoint for deployments that import ``backend.app.main``.

The actively maintained API lives in :mod:`backend.main`.  Re-exporting the same
FastAPI app here keeps older README commands and ASGI configurations working
without requiring the removed SQLAlchemy scaffold.
"""

from backend.main import app

__all__ = ["app"]
