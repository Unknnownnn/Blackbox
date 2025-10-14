from datetime import datetime
from models import db

class Settings(db.Model):
    """Settings model for CTF configuration"""
    __tablename__ = 'settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    value = db.Column(db.Text)
    value_type = db.Column(db.String(20), default='string')  # string, int, bool, datetime
    description = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @staticmethod
    def get(key, default=None, type=None):
        """Get setting value by key"""
        setting = Settings.query.filter_by(key=key).first()
        if not setting:
            return default
        
        # Use provided type or setting's value_type
        value_type = type or setting.value_type
        
        # Convert value based on type
        if value_type == 'bool':
            return setting.value.lower() in ('true', '1', 'yes', 'on')
        elif value_type == 'int':
            return int(setting.value) if setting.value else default
        elif value_type == 'datetime':
            from dateutil import parser
            return parser.parse(setting.value) if setting.value else default
        else:
            return setting.value if setting.value else default
    
    @staticmethod
    def set(key, value, value_type='string', description=None):
        """Set setting value by key"""
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
        return setting
    
    @staticmethod
    def get_all():
        """Get all settings as dictionary"""
        settings = Settings.query.all()
        return {s.key: Settings.get(s.key) for s in settings}
    
    @staticmethod
    def is_ctf_started():
        """Check if CTF has started"""
        start_time = Settings.get('ctf_start_time')
        if not start_time:
            return True  # No start time set, CTF is always running
        return datetime.utcnow() >= start_time
    
    @staticmethod
    def is_ctf_ended():
        """Check if CTF has ended"""
        end_time = Settings.get('ctf_end_time')
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
        return Settings.get('ctf_paused', False)
    
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
