import os
from dotenv import load_dotenv
from sqlalchemy.pool import NullPool

# Load environment variables
load_dotenv()

class Config:
    """Base configuration"""
    
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    FLASK_APP = os.getenv('FLASK_APP', 'app.py')
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    DEBUG = os.getenv('DEBUG', 'true').lower() == 'true'
    
    # Database
    DATABASE_USER = os.getenv('DATABASE_USER', 'blackbox_user')
    DATABASE_PASSWORD = os.getenv('DATABASE_PASSWORD', 'blackbox_password')
    DATABASE_HOST = os.getenv('DATABASE_HOST', 'localhost')
    DATABASE_PORT = os.getenv('DATABASE_PORT', '3306')
    DATABASE_NAME = os.getenv('DATABASE_NAME', 'ctf_platform')
    
    # Support DATABASE_URL for Docker deployment
    DATABASE_URL = os.getenv('DATABASE_URL')
    if DATABASE_URL:
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
    else:
        SQLALCHEMY_DATABASE_URI = (
            f"mysql+pymysql://{DATABASE_USER}:{DATABASE_PASSWORD}"
            f"@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}?charset=utf8mb4"
        )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Connection pooling for high concurrency (safe with eventlet)
    # Each worker process gets its own pool (workers are separate processes, not threads)
    SQLALCHEMY_ENGINE_OPTIONS = {
        # Connection pool settings (per worker)
        'pool_size': 5,              # Persistent connections per worker
        'max_overflow': 10,          # Additional connections when busy (total = 15 per worker)
        'pool_timeout': 30,          # Wait 30s for available connection
        'pool_recycle': 3600,        # Recycle connections after 1 hour
        'pool_pre_ping': True,       # Test connection before use (detect stale connections)
        
        # Critical for multi-worker deployments
        'pool_reset_on_return': 'rollback',  # Reset connection state on return to pool
        'echo_pool': False,          # Disable pool logging for performance
    }
    
    # Redis
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    REDIS_DB = int(os.getenv('REDIS_DB', 0))
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)
    
    # Support REDIS_URL for Docker deployment
    REDIS_URL = os.getenv('REDIS_URL')
    if not REDIS_URL:
        REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    
    # Cache
    CACHE_TYPE = "redis"
    CACHE_REDIS_URL = REDIS_URL
    CACHE_DEFAULT_TIMEOUT = 300
    
    # Application
    CTF_NAME = os.getenv('CTF_NAME', 'BlackBox CTF')
    CTF_DESCRIPTION = os.getenv('CTF_DESCRIPTION', 'Capture The Flag Competition')
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@blackbox.ctf')
    REGISTRATION_ENABLED = os.getenv('REGISTRATION_ENABLED', 'true').lower() == 'true'
    TEAM_SIZE = int(os.getenv('TEAM_SIZE', 4))
    
    # Scoring
    DYNAMIC_SCORING = os.getenv('DYNAMIC_SCORING', 'true').lower() == 'true'
    MIN_CHALLENGE_POINTS = int(os.getenv('MIN_CHALLENGE_POINTS', 50))
    MAX_CHALLENGE_POINTS = int(os.getenv('MAX_CHALLENGE_POINTS', 500))
    DECAY_FUNCTION = os.getenv('DECAY_FUNCTION', 'logarithmic')
    
    # Server
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 5000))
    
    # File Upload
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads'))
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_UPLOAD_SIZE', 50 * 1024 * 1024))  # 50MB default
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'zip', 
                         'tar', 'gz', 'bz2', '7z', 'rar', 'exe', 'bin', 
                         'pcap', 'pcapng', 'cap', 'py', 'c', 'cpp', 'java',
                         'js', 'html', 'css', 'json', 'xml', 'yaml', 'yml'}
    
    # Session
    SESSION_TYPE = 'filesystem'
    PERMANENT_SESSION_LIFETIME = 3600 * 24  # 24 hours
    SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
    SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access to session cookie
    SESSION_COOKIE_SAMESITE = 'Lax'  # CSRF protection
    SESSION_COOKIE_NAME = 'blackbox_session'
    
    # Security
    # These headers are managed by security_utils.py
    # Additional security settings can be added here

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False  # Allow HTTP in development

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True  # Require HTTPS in production
    # Force HTTPS redirects (if using Flask-Talisman or similar)
    PREFERRED_URL_SCHEME = 'https'

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
