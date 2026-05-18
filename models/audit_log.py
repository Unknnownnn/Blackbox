from datetime import datetime
from models import db

class AuditLog(db.Model):
    """AuditLog model for tracking IP addresses and user actions"""
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id', ondelete='CASCADE'), nullable=True)
    ip_address = db.Column(db.String(45), nullable=False, index=True)
    action = db.Column(db.String(50), nullable=False) # e.g., 'LOGIN_SUCCESS', 'REGISTER', 'SUBMIT_FLAG', 'JOIN_TEAM'
    details = db.Column(db.JSON, nullable=True)       # Contextual info
    user_agent = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    # NOTE: cascade is intentionally limited to 'all' (save-update, merge, expunge, delete)
    # and does NOT include 'delete-orphan', because both user_id and team_id are nullable.
    # Deletion from the DB side is handled by the FK-level ON DELETE CASCADE constraints.
    user = db.relationship('User', backref=db.backref('audit_logs', lazy='dynamic', cascade='all'))
    team = db.relationship('Team', backref=db.backref('audit_logs', lazy='dynamic', cascade='all'))
    
    def to_dict(self):
        """Convert log to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'team_id': self.team_id,
            'ip_address': self.ip_address,
            'action': self.action,
            'details': self.details,
            'user_agent': self.user_agent,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }
    
    def __repr__(self):
        return f'<AuditLog {self.action} by User:{self.user_id} IP:{self.ip_address}>'
