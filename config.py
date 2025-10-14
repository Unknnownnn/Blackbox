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
    DATABASE_USER = os.getenv('DATABASE_USER', 'ctf_user')
    DATABASE_PASSWORD = os.getenv('DATABASE_PASSWORD', 'ctf_password')
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
    # Use NullPool with eventlet to avoid threading lock issues
    # NullPool recreates connections on each request, preventing pool contention
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'poolclass': NullPool,  # Critical for eventlet compatibility
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
    CTF_NAME = os.getenv('CTF_NAME', 'CTF Platform')
    CTF_DESCRIPTION = os.getenv('CTF_DESCRIPTION', 'Capture The Flag Competition')
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@example.com')
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

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False

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
