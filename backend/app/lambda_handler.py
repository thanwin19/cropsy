"""
lambda_handler.py — AWS Lambda entry point via Mangum.
"""
from __future__ import annotations

try:
    from mangum import Mangum
    from app.main import app
    handler = Mangum(app, lifespan="off")
except ImportError:
    # Mangum not installed in dev environment
    handler = None
