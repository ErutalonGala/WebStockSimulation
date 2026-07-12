"""Compatibility entrypoint for deployments that import ``backend.app.main``.

The maintained API lives in :mod:`backend.main`.  When this module is imported
as ``app.main`` from inside the ``backend`` directory, Python would normally be
unable to resolve the repository-root ``backend`` package.  Add that root to
``sys.path`` before importing the canonical app so both documented Uvicorn
commands keep working.
"""

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
repo_root = str(REPO_ROOT)
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from backend.main import app

__all__ = ["app"]
