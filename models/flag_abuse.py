"""
Flag Abuse Tracking Model
Tracks attempts to submit flags that belong to other teams (flag sharing)
"""

from models import db
from datetime import datetime


class FlagAbuseAttempt(db.Model):
    """Track flag sharing attempts"""
    __tablename__ = 'flag_abuse_attempts'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Who tried to submit the flag
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=True)
    
    # Which challenge
    challenge_id = db.Column(db.Integer, db.ForeignKey('challenges.id'), nullable=False)
    
    # The flag they submitted
    submitted_flag = db.Column(db.String(512), nullable=False)
    
    # Which team does the flag actually belong to
    actual_team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=True)
    actual_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Metadata
    ip_address = db.Column(db.String(45), nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Abuse severity (for future use)
    severity = db.Column(db.String(20), default='warning')  # warning, suspicious, critical
    notes = db.Column(db.Text, nullable=True)
    
    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref='flag_abuse_attempts')
    team = db.relationship('Team', foreign_keys=[team_id], backref='flag_abuse_attempts')
    challenge = db.relationship('Challenge', backref='flag_abuse_attempts')
    actual_team = db.relationship('Team', foreign_keys=[actual_team_id])
    actual_user = db.relationship('User', foreign_keys=[actual_user_id])
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user_name': self.user.username if self.user else None,
            'team_id': self.team_id,
            'team_name': self.team.name if self.team else None,
            'challenge_id': self.challenge_id,
            'challenge_name': self.challenge.name if self.challenge else None,
            'submitted_flag': self.submitted_flag[:50] + '...' if len(self.submitted_flag) > 50 else self.submitted_flag,
            'actual_team_id': self.actual_team_id,
            'actual_team_name': self.actual_team.name if self.actual_team else None,
            'actual_user_id': self.actual_user_id,
            'actual_user_name': self.actual_user.username if self.actual_user else None,
            'ip_address': self.ip_address,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'severity': self.severity,
            'notes': self.notes
        }
    
    def __repr__(self):
        return f'<FlagAbuseAttempt user={self.user_id} challenge={self.challenge_id}>'

    # Convenience properties for templates
    @property
    def user_name(self):
        return self.user.username if self.user else None

    @property
    def team_name(self):
        return self.team.name if self.team else None

    @property
    def actual_team_name(self):
        return self.actual_team.name if self.actual_team else None

    @property
    def actual_user_name(self):
        return self.actual_user.username if self.actual_user else None

    @property
    def challenge_name(self):
        return self.challenge.name if self.challenge else None
