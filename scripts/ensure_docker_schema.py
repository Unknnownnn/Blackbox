#!/usr/bin/env python3
"""
Ensure Docker settings table has required columns and a default row.
This script is safe to run on startup and is idempotent.
"""
import sys
import os

# Add parent directory to path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app import create_app

app = create_app()

with app.app_context():
    try:
        from scripts.db_schema import ensure_docker_schema
        ensure_docker_schema()
        print("Docker schema check complete")
    except Exception as e:
        print(f"Failed to ensure docker schema: {e}")
        sys.exit(1)
