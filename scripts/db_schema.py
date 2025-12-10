"""
Database schema helpers for ensuring required columns and default DockerSettings.

This module exposes a single function `ensure_docker_schema` which must be
called with an active Flask application context (so `models.db` is configured).
The function is idempotent and safe to call at app startup.
"""
from sqlalchemy import text
from models import db
from models.settings import DockerSettings


def ensure_docker_schema():
    """Ensure required docker-related columns and default DockerSettings exist.

    Must be called inside a Flask application context.
    """
    alter_statements = [
        # Use MySQL 8+ syntax where available; errors will be caught and ignored
        "ALTER TABLE docker_settings ADD COLUMN IF NOT EXISTS max_cpu_percent FLOAT DEFAULT 50.0;",
        "ALTER TABLE docker_settings ADD COLUMN IF NOT EXISTS max_memory_mb INT DEFAULT 128;",
        "ALTER TABLE docker_settings ADD COLUMN IF NOT EXISTS auto_cleanup_expired BOOLEAN DEFAULT TRUE;",
        "ALTER TABLE docker_settings ADD COLUMN IF NOT EXISTS cleanup_interval_minutes INT DEFAULT 5;",
        "ALTER TABLE docker_settings ADD COLUMN IF NOT EXISTS max_concurrent_containers INT DEFAULT 50;",
        # container_instances dynamic flag storage
        "ALTER TABLE container_instances ADD COLUMN IF NOT EXISTS dynamic_flag VARCHAR(512) DEFAULT NULL;",
        # challenges table: admin-configured in-container flag path
        "ALTER TABLE challenges ADD COLUMN IF NOT EXISTS docker_flag_path VARCHAR(256) DEFAULT NULL;",
    ]
    
    # Create flag_abuse_attempts table if not exists
    create_tables = [
        """
        CREATE TABLE IF NOT EXISTS flag_abuse_attempts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            team_id INT NULL,
            challenge_id INT NOT NULL,
            submitted_flag VARCHAR(512) NOT NULL,
            actual_team_id INT NULL,
            actual_user_id INT NULL,
            ip_address VARCHAR(45) NULL,
            timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            severity VARCHAR(20) DEFAULT 'warning',
            notes TEXT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
            FOREIGN KEY (challenge_id) REFERENCES challenges(id) ON DELETE CASCADE,
            FOREIGN KEY (actual_team_id) REFERENCES teams(id) ON DELETE SET NULL,
            FOREIGN KEY (actual_user_id) REFERENCES users(id) ON DELETE SET NULL,
            INDEX idx_user_id (user_id),
            INDEX idx_team_id (team_id),
            INDEX idx_challenge_id (challenge_id),
            INDEX idx_timestamp (timestamp)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
    ]

    conn = db.engine.connect()
    
    # Create tables first
    for stmt in create_tables:
        try:
            conn.execute(text(stmt))
        except Exception:
            # Ignore individual failures
            pass
    
    # Then alter existing tables
    for stmt in alter_statements:
        try:
            conn.execute(text(stmt))
        except Exception:
            # Ignore individual failures; we'll still try to ensure defaults below
            pass

    # Ensure a default DockerSettings row exists and fill any missing defaults
    cfg = DockerSettings.query.first()
    if not cfg:
        cfg = DockerSettings(
            hostname='',
            tls_enabled=False,
            allowed_repositories='ctf-*',
            max_containers_per_user=1,
            container_lifetime_minutes=15,
            port_range_start=30000,
            port_range_end=50000,
            max_cpu_percent=50.0,
            max_memory_mb=128,
            revert_cooldown_minutes=5,
            auto_cleanup_on_solve=True,
            auto_cleanup_expired=True,
            cleanup_interval_minutes=5,
            cleanup_stale_containers=True,
            stale_container_hours=2,
            max_concurrent_containers=50
        )
        db.session.add(cfg)
        db.session.commit()
    else:
        changed = False
        if not hasattr(cfg, 'max_cpu_percent') or cfg.max_cpu_percent is None:
            cfg.max_cpu_percent = 50.0
            changed = True
        if not hasattr(cfg, 'max_memory_mb') or cfg.max_memory_mb is None:
            cfg.max_memory_mb = 128
            changed = True
        if not hasattr(cfg, 'auto_cleanup_expired') or cfg.auto_cleanup_expired is None:
            cfg.auto_cleanup_expired = True
            changed = True
        if not hasattr(cfg, 'cleanup_interval_minutes') or cfg.cleanup_interval_minutes is None:
            cfg.cleanup_interval_minutes = 5
            changed = True
        if not hasattr(cfg, 'max_concurrent_containers') or cfg.max_concurrent_containers is None:
            cfg.max_concurrent_containers = 50
            changed = True
        # Update old default values to new defaults
        if getattr(cfg, 'container_lifetime_minutes', None) == 120:
            cfg.container_lifetime_minutes = 15
            changed = True
        if changed:
            db.session.commit()

    conn.close()
