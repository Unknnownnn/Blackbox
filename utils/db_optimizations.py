# Database Query Optimization Configuration

"""
This module configures database engine settings for optimal performance.
Import and call init_db_optimizations() in your app factory.
"""

from sqlalchemy import event
from sqlalchemy.engine import Engine
from flask_sqlalchemy import SQLAlchemy
import logging

logger = logging.getLogger(__name__)


def init_db_optimizations(app, db):
    """
    Initialize database optimizations
    
    Usage in app.py:
        from utils.db_optimizations import init_db_optimizations
        init_db_optimizations(app, db)
    """
    
    # 1. Enable query logging in development (for debugging)
    if app.config.get('DEBUG', False):
        @event.listens_for(Engine, "before_cursor_execute")
        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            conn.info.setdefault('query_start_time', []).append(time.time())
            
        @event.listens_for(Engine, "after_cursor_execute")
        def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            total = time.time() - conn.info['query_start_time'].pop(-1)
            if total > 0.1:  # Log slow queries (> 100ms)
                logger.warning(f'Slow query ({total:.3f}s): {statement[:200]}...')
    
    # 2. Configure connection pool
    app.config.setdefault('SQLALCHEMY_ENGINE_OPTIONS', {})
    engine_options = app.config['SQLALCHEMY_ENGINE_OPTIONS']
    
    # Pool settings for better concurrency
    engine_options.setdefault('pool_size', 10)  # Number of persistent connections
    engine_options.setdefault('max_overflow', 20)  # Additional connections when pool is full
    engine_options.setdefault('pool_timeout', 30)  # Seconds to wait for connection
    engine_options.setdefault('pool_recycle', 3600)  # Recycle connections after 1 hour
    engine_options.setdefault('pool_pre_ping', True)  # Test connections before use
    
    # 3. MySQL-specific optimizations
    if 'mysql' in app.config.get('SQLALCHEMY_DATABASE_URI', ''):
        # Enable query cache on MySQL side
        @event.listens_for(Engine, "connect")
        def set_mysql_options(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            # Enable query cache
            cursor.execute("SET SESSION query_cache_type = ON")
            # Set character set
            cursor.execute("SET NAMES utf8mb4")
            cursor.execute("SET CHARACTER SET utf8mb4")
            cursor.close()
    
    logger.info("Database optimizations initialized")


def add_query_profiling_middleware(app):
    """
    Add middleware to profile database queries per request
    Only enable in development!
    """
    if not app.config.get('DEBUG', False):
        return
    
    from flask import g, request
    import time
    
    @app.before_request
    def before_request():
        g.start_time = time.time()
        g.query_count = 0
        g.query_time = 0
    
    @app.after_request
    def after_request(response):
        if hasattr(g, 'start_time'):
            request_time = time.time() - g.start_time
            
            # Log slow requests
            if request_time > 0.5:  # > 500ms
                logger.warning(
                    f'Slow request: {request.method} {request.path} '
                    f'({request_time:.3f}s, {g.get("query_count", 0)} queries, '
                    f'{g.get("query_time", 0):.3f}s in DB)'
                )
        
        return response


# Query optimization helper functions
def bulk_insert(model_class, data_list):
    """
    Bulk insert multiple records efficiently
    
    Usage:
        from utils.db_optimizations import bulk_insert
        
        data = [
            {'name': 'Challenge 1', 'category': 'Web'},
            {'name': 'Challenge 2', 'category': 'Crypto'},
        ]
        bulk_insert(Challenge, data)
    """
    from models import db
    
    objects = [model_class(**data) for data in data_list]
    db.session.bulk_save_objects(objects)
    db.session.commit()


def bulk_update(model_class, updates):
    """
    Bulk update multiple records efficiently
    
    Usage:
        from utils.db_optimizations import bulk_update
        
        updates = [
            {'id': 1, 'points': 450},
            {'id': 2, 'points': 400},
        ]
        bulk_update(Challenge, updates)
    """
    from models import db
    
    db.session.bulk_update_mappings(model_class, updates)
    db.session.commit()


def optimize_pagination(query, page=1, per_page=20):
    """
    Optimize pagination queries
    
    Usage:
        from utils.db_optimizations import optimize_pagination
        
        query = Challenge.query.filter_by(is_visible=True)
        pagination = optimize_pagination(query, page=1, per_page=20)
        
        # Access results
        challenges = pagination.items
        total_pages = pagination.pages
    """
    # Use efficient LIMIT/OFFSET
    return query.paginate(
        page=page,
        per_page=per_page,
        error_out=False,  # Don't raise error for invalid page
        max_per_page=100  # Cap max items per page
    )


# Database maintenance functions
def analyze_tables():
    """
    Run ANALYZE on all tables to update statistics
    Should be run periodically (e.g., daily cron job)
    """
    from models import db
    
    tables = [
        'users', 'teams', 'challenges', 'submissions', 'solves',
        'settings', 'challenge_files', 'hints', 'hint_unlocks'
    ]
    
    for table in tables:
        try:
            db.session.execute(f'ANALYZE TABLE {table}')
            logger.info(f'Analyzed table: {table}')
        except Exception as e:
            logger.error(f'Failed to analyze table {table}: {e}')
    
    db.session.commit()


def optimize_tables():
    """
    Optimize all tables to reclaim space and improve performance
    Should be run weekly
    """
    from models import db
    
    tables = [
        'users', 'teams', 'challenges', 'submissions', 'solves',
        'settings', 'challenge_files', 'hints', 'hint_unlocks'
    ]
    
    for table in tables:
        try:
            db.session.execute(f'OPTIMIZE TABLE {table}')
            logger.info(f'Optimized table: {table}')
        except Exception as e:
            logger.error(f'Failed to optimize table {table}: {e}')
    
    db.session.commit()


# Import time fix
import time

