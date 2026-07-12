"""Compatibility package for ``uvicorn app.main:app`` from the repo root."""

from backend.main import app

__all__ = ["app"]
