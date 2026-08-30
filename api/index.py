"""
Vercel entry point.

Vercel's Python runtime serves any ASGI app exported as `app` from a file under
api/. This just puts the project root on the path and re-exports the FastAPI
app, so there is one application definition, not two.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: E402

__all__ = ["app"]
