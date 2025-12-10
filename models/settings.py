from datetime import datetime
from models import db
from flask import current_app
import json

class Settings(db.Model):
    """Settings model for CTF configuration with Redis caching"""
    __tablename__ = 'settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    value = db.Column(db.Text)
    value_type = db.Column(db.String(20), default='string')  # string, int, bool, datetime
    description = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Redis cache configuration (distributed across all workers)
    CACHE_PREFIX = 'settings:'
    CACHE_TIMEOUT = 300  # 5 minutes
    CACHE_ALL_KEY = 'settings:all'
    
    @staticmethod
    def _get_cache():
        """Get Redis cache instance"""
        from services.cache import cache_service
        return cache_service
    
    @staticmethod
    def _cache_key(key):
        """Generate cache key"""
        return f"{Settings.CACHE_PREFIX}{key}"
    
    @staticmethod
    def get(key, default=None, type=None):
        """Get setting value by key with distributed Redis caching"""
        try:
            cache = Settings._get_cache()
            cache_key = Settings._cache_key(key)
            
            # Try Redis cache first
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                # Cache hit - parse and return
                if isinstance(cached_value, dict):
                    value = cached_value.get('value')
                    value_type = type or cached_value.get('type', 'string')
                else:
                    value = cached_value
                    value_type = type or 'string'
                
                return Settings._convert_value(value, value_type, default)
            
            # Cache miss - query database with lock to prevent cache stampede
            lock_key = f"lock:{cache_key}"
            if cache.redis_client.set(lock_key, '1', ex=10, nx=True):
                # We got the lock - load from database
                try:
                    setting = Settings.query.filter_by(key=key).first()
                    if setting:
                        # Cache the result
                        cache_data = {
                            'value': setting.value,
                            'type': setting.value_type
                        }
                        cache.set(cache_key, cache_data, ttl=Settings.CACHE_TIMEOUT)
                        
                        value_type = type or setting.value_type
                        return Settings._convert_value(setting.value, value_type, default)
                    else:
                        # Cache negative result (key doesn't exist)
                        cache.set(cache_key, {'value': None, 'type': 'none'}, ttl=60)
                        return default
                finally:
                    cache.redis_client.delete(lock_key)
            else:
                # Lock held by another request - wait briefly and retry from cache
                import time
                time.sleep(0.05)  # 50ms wait
                cached_value = cache.get(cache_key)
                if cached_value and isinstance(cached_value, dict):
                    value = cached_value.get('value')
                    value_type = type or cached_value.get('type', 'string')
                    return Settings._convert_value(value, value_type, default)
        except Exception as e:
            # If cache fails, fall back to direct database query
            print(f"Settings cache error: {e}")
            setting = Settings.query.filter_by(key=key).first()
            if setting:
                value_type = type or setting.value_type
                return Settings._convert_value(setting.value, value_type, default)
        
        return default
    
    @staticmethod
    def _convert_value(value, value_type, default):
        """Convert cached value to correct type"""
        if value is None:
            return default
        
        try:
            if value_type == 'bool':
                return str(value).lower() in ('true', '1', 'yes', 'on')
            elif value_type == 'int':
                return int(value)
            elif value_type == 'datetime':
                from dateutil import parser
                return parser.parse(value)
            else:
                return value
        except:
            return default
    
    @staticmethod
    def set(key, value, value_type='string', description=None):
        """Set setting value by key and invalidate distributed cache"""
        setting = Settings.query.filter_by(key=key).first()
        
        if not setting:
            setting = Settings(key=key, value_type=value_type, description=description)
            db.session.add(setting)
        
        # Convert value to string for storage
        if value_type == 'bool':
            setting.value = 'true' if value else 'false'
        elif value_type == 'datetime':
            setting.value = value.isoformat() if value else None
        else:
            setting.value = str(value) if value is not None else None
        
        setting.value_type = value_type
        if description:
            setting.description = description
        
        db.session.commit()
        
        # Invalidate cache across ALL workers (distributed via Redis)
        Settings.clear_cache(key)
        
        return setting
    
    @staticmethod
    def clear_cache(key=None):
        """Clear settings cache in Redis (affects ALL workers)"""
        try:
            cache = Settings._get_cache()
            
            if key:
                # Clear specific key
                cache.delete(Settings._cache_key(key))
            else:
                # Clear all settings caches
                keys = cache.redis_client.keys(f"{Settings.CACHE_PREFIX}*")
                if keys:
                    cache.redis_client.delete(*keys)
            
            # Also clear the "all settings" cache
            cache.delete(Settings.CACHE_ALL_KEY)
        except Exception as e:
            print(f"Error clearing settings cache: {e}")
    
    @staticmethod
    def get_all():
        """Get all settings as dictionary with batch caching"""
        try:
            cache = Settings._get_cache()
            
            # Try cache first
            cached = cache.get(Settings.CACHE_ALL_KEY)
            if cached:
                return cached
            
            # Cache miss - load all settings
            settings = Settings.query.all()
            result = {s.key: Settings.get(s.key) for s in settings}
            
            # Cache the complete dictionary
            cache.set(Settings.CACHE_ALL_KEY, result, ttl=Settings.CACHE_TIMEOUT)
            
            return result
        except Exception as e:
            # Fallback to direct database query
            print(f"Error getting all settings from cache: {e}")
            settings = Settings.query.all()
            return {s.key: Settings.get(s.key) for s in settings}
    
    @staticmethod
    def is_ctf_started():
        """Check if CTF has started"""
        start_time = Settings.get('ctf_start_time', type='datetime')
        if not start_time:
            return True  # No start time set, CTF is always running
        return datetime.utcnow() >= start_time
    
    @staticmethod
    def is_ctf_ended():
        """Check if CTF has ended"""
        end_time = Settings.get('ctf_end_time', type='datetime')
        if not end_time:
            return False  # No end time set, CTF never ends
        return datetime.utcnow() >= end_time
    
    @staticmethod
    def is_ctf_running():
        """Check if CTF is currently running"""
        return Settings.is_ctf_started() and not Settings.is_ctf_ended() and not Settings.is_ctf_paused()
    
    @staticmethod
    def is_ctf_paused():
        """Check if CTF is paused"""
        return Settings.get('ctf_paused', False, type='bool')
    
    @staticmethod
    def get_ctf_status():
        """Get current CTF status"""
        if not Settings.is_ctf_started():
            return 'not_started'
        elif Settings.is_ctf_ended():
            return 'ended'
        elif Settings.is_ctf_paused():
            return 'paused'
        else:
            return 'running'
    
    def to_dict(self):
        """Convert setting to dictionary"""
        return {
            'key': self.key,
            'value': Settings.get(self.key),
            'value_type': self.value_type,
            'description': self.description,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<Settings {self.key}={self.value}>'


class DockerSettings(db.Model):
    """Docker daemon connection and orchestration settings"""
    __tablename__ = 'docker_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Docker daemon connection
    hostname = db.Column(db.String(256))  # e.g., "tcp://10.10.10.10:2376" or empty for local socket
    tls_enabled = db.Column(db.Boolean, default=False)
    ca_cert = db.Column(db.Text)  # PEM format
    client_cert = db.Column(db.Text)  # PEM format
    client_key = db.Column(db.Text)  # PEM format
    
    # Repository whitelist (one per line)
    allowed_repositories = db.Column(db.Text)  # Newline-separated list of allowed image prefixes
    
    # Resource limits
    max_containers_per_user = db.Column(db.Integer, default=1)
    container_lifetime_minutes = db.Column(db.Integer, default=15)  # 15 minutes
    revert_cooldown_minutes = db.Column(db.Integer, default=5)
    
    # Port range for container mapping
    port_range_start = db.Column(db.Integer, default=30000)
    port_range_end = db.Column(db.Integer, default=60000)
    
    # Resource limits
    max_cpu_percent = db.Column(db.Float, default=50.0)
    max_memory_mb = db.Column(db.Integer, default=512)
    
    # Auto-cleanup settings
    auto_cleanup_on_solve = db.Column(db.Boolean, default=True)
    auto_cleanup_expired = db.Column(db.Boolean, default=True)
    cleanup_interval_minutes = db.Column(db.Integer, default=5)
    cleanup_stale_containers = db.Column(db.Boolean, default=True)
    stale_container_hours = db.Column(db.Integer, default=2)
    
    # Global limits
    max_concurrent_containers = db.Column(db.Integer, default=50)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @staticmethod
    def get_config():
        """Get Docker configuration (singleton pattern)"""
        config = DockerSettings.query.first()
        if not config:
            # Create default config
            config = DockerSettings()
            db.session.add(config)
            db.session.commit()
        return config
    
    def get_allowed_repositories_list(self):
        """Get list of allowed repository prefixes"""
        if not self.allowed_repositories:
            return []
        return [r.strip() for r in self.allowed_repositories.split('\n') if r.strip()]
    
    def is_image_allowed(self, image_name):
        """Check if an image is in the allowed repositories"""
        allowed = self.get_allowed_repositories_list()
        if not allowed:
            return True  # No whitelist = allow all
        
        return any(image_name.startswith(repo) for repo in allowed)
    
    def to_dict(self):
        """Convert to dictionary (excluding sensitive data)"""
        return {
            'id': self.id,
            'hostname': self.hostname,
            'tls_enabled': self.tls_enabled,
            'has_certificates': bool(self.ca_cert and self.client_cert and self.client_key),
            'max_containers_per_user': self.max_containers_per_user,
            'container_lifetime_minutes': self.container_lifetime_minutes,
            'revert_cooldown_minutes': self.revert_cooldown_minutes,
            'port_range_start': self.port_range_start,
            'port_range_end': self.port_range_end,
            'auto_cleanup_on_solve': self.auto_cleanup_on_solve,
            'allowed_repositories_count': len(self.get_allowed_repositories_list()),
            'max_concurrent_containers': self.max_concurrent_containers
        }
    
    def __repr__(self):
        return f'<DockerSettings hostname={self.hostname} tls={self.tls_enabled}>'
