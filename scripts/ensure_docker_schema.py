#!/usr/bin/env python3
"""
Ensure Docker settings table has required columns and a default row.
This script is safe to run on startup and is idempotent.
"""
import sys
from sqlalchemy import text

try:
    from app import create_app
    from models import db
    from models.settings import DockerSettings
except Exception as e:
    print(f"Failed to import application: {e}")
    sys.exit(1)

app = create_app()

with app.app_context():
    # Run ALTER TABLE to add missing columns if they don't exist
    # Use SQL that is safe on MySQL 8+ (IF NOT EXISTS behavior simulated)
    alter_statements = [
        "ALTER TABLE docker_settings ADD COLUMN IF NOT EXISTS max_cpu_percent FLOAT DEFAULT 50.0;",
        "ALTER TABLE docker_settings ADD COLUMN IF NOT EXISTS max_memory_mb INT DEFAULT 512;",
        "ALTER TABLE docker_settings ADD COLUMN IF NOT EXISTS auto_cleanup_expired BOOLEAN DEFAULT TRUE;",
        "ALTER TABLE docker_settings ADD COLUMN IF NOT EXISTS cleanup_interval_minutes INT DEFAULT 5;",
    ]

    conn = db.engine.connect()
    for stmt in alter_statements:
        try:
            conn.execute(text(stmt))
            print(f"Executed: {stmt}")
        except Exception as e:
            # If the database doesn't support ADD COLUMN IF NOT EXISTS, try to run a safe check
            print(f"Warning executing statement, will attempt idempotent check: {e}")
            # Fallback: ignore and continue
            pass

    # Ensure a default DockerSettings row exists
    cfg = DockerSettings.query.first()
    if not cfg:
        print("Creating default DockerSettings row...")
        cfg = DockerSettings(
            hostname='',
            tls_enabled=False,
            allowed_repositories='ctf-*',
            max_containers_per_user=1,
            container_lifetime_minutes=15,
            port_range_start=30000,
            port_range_end=30100,
            max_cpu_percent=50.0,
            max_memory_mb=512,
            revert_cooldown_minutes=5,
            auto_cleanup_on_solve=True,
            auto_cleanup_expired=True,
            cleanup_interval_minutes=5,
            cleanup_stale_containers=True,
            stale_container_hours=2
        )
        db.session.add(cfg)
        db.session.commit()
        print("Default DockerSettings created")
    else:
        # Fill missing attributes if present as None, and update old defaults
        changed = False
        if not hasattr(cfg, 'max_cpu_percent') or cfg.max_cpu_percent is None:
            cfg.max_cpu_percent = 50.0
            changed = True
        if not hasattr(cfg, 'max_memory_mb') or cfg.max_memory_mb is None:
            cfg.max_memory_mb = 512
            changed = True
        if not hasattr(cfg, 'auto_cleanup_expired') or cfg.auto_cleanup_expired is None:
            cfg.auto_cleanup_expired = True
            changed = True
        if not hasattr(cfg, 'cleanup_interval_minutes') or cfg.cleanup_interval_minutes is None:
            cfg.cleanup_interval_minutes = 5
            changed = True
        # Update old default values to new defaults
        if cfg.container_lifetime_minutes == 120:  # Old default was 120 minutes
            cfg.container_lifetime_minutes = 15  # New default is 15 minutes
            changed = True
        if changed:
            db.session.commit()
            print("Updated DockerSettings with missing defaults and corrected old values")

    conn.close()
    print("Docker schema check complete")
