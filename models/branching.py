"""
Challenge branching models
Handles multiple flags, prerequisites, and flag-based challenge unlocking
"""

from datetime import datetime
from models import db
import re


class ChallengeFlag(db.Model):
    """Model for multiple flags per challenge with branching support"""
    __tablename__ = 'challenge_flags'
    
    id = db.Column(db.Integer, primary_key=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey('challenges.id'), nullable=False, index=True)
    
    # Flag details
    flag_value = db.Column(db.String(255), nullable=False)
    flag_label = db.Column(db.String(100))  # User-friendly label for admin
    is_case_sensitive = db.Column(db.Boolean, default=True)
    
    # Regex flag support
    is_regex = db.Column(db.Boolean, default=False)
    
    # Branching: which challenge does this flag unlock?
    unlocks_challenge_id = db.Column(db.Integer, db.ForeignKey('challenges.id'), nullable=True, index=True)
    
    # Points override (NULL = use challenge's default points)
    points_override = db.Column(db.Integer, nullable=True)
    
    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    challenge = db.relationship('Challenge', foreign_keys=[challenge_id], backref='flags')
    unlocks_challenge = db.relationship('Challenge', foreign_keys=[unlocks_challenge_id])
    
    def check_flag(self, submitted_flag, team_id=None, user_id=None):
        """Check if submitted flag matches this flag
        
        Args:
            submitted_flag: The flag submitted by the user
            team_id: Optional team_id (for future use)
            user_id: Optional user_id (for future use)
            
        Returns:
            bool: True if flag matches, False otherwise
        """
        # Handle regex flags
        if self.is_regex:
            try:
                if self.is_case_sensitive:
                    pattern = re.compile(self.flag_value)
                else:
                    pattern = re.compile(self.flag_value, re.IGNORECASE)
                return pattern.fullmatch(submitted_flag) is not None
            except re.error:
                # Invalid regex pattern, fall back to exact match
                pass
        
        # Standard static flag comparison
        if self.is_case_sensitive:
            return submitted_flag == self.flag_value
        else:
            return submitted_flag.lower() == self.flag_value.lower()
    
    def to_dict(self, include_value=False):
        """Convert to dictionary"""
        data = {
            'id': self.id,
            'challenge_id': self.challenge_id,
            'label': self.flag_label,
            'unlocks_challenge_id': self.unlocks_challenge_id,
            'points_override': self.points_override,
            'is_case_sensitive': self.is_case_sensitive,
            'is_regex': self.is_regex
        }
        
        if include_value:
            data['flag_value'] = self.flag_value
        
        return data
    
    def __repr__(self):
        return f'<ChallengeFlag {self.id} for Challenge {self.challenge_id}>'


class ChallengePrerequisite(db.Model):
    """Model for challenge prerequisites (must solve A before seeing B)"""
    __tablename__ = 'challenge_prerequisites'
    
    id = db.Column(db.Integer, primary_key=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey('challenges.id'), nullable=False, index=True)
    prerequisite_challenge_id = db.Column(db.Integer, db.ForeignKey('challenges.id'), nullable=False, index=True)
    
    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    challenge = db.relationship('Challenge', foreign_keys=[challenge_id], backref='prerequisites')
    prerequisite_challenge = db.relationship('Challenge', foreign_keys=[prerequisite_challenge_id])
    
    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('challenge_id', 'prerequisite_challenge_id', name='unique_prerequisite'),
    )
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'challenge_id': self.challenge_id,
            'prerequisite_challenge_id': self.prerequisite_challenge_id,
            'prerequisite_name': self.prerequisite_challenge.name if self.prerequisite_challenge else None
        }
    
    def __repr__(self):
        return f'<ChallengePrerequisite {self.challenge_id} requires {self.prerequisite_challenge_id}>'


class ChallengeUnlock(db.Model):
    """Model for tracking which challenges were unlocked by which flags"""
    __tablename__ = 'challenge_unlocks'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=True, index=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey('challenges.id'), nullable=False, index=True)
    unlocked_by_flag_id = db.Column(db.Integer, db.ForeignKey('challenge_flags.id'), nullable=False)
    
    # Timestamp
    unlocked_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='challenge_unlocks')
    team = db.relationship('Team', backref='challenge_unlocks')
    challenge = db.relationship('Challenge', backref='unlocks')
    flag = db.relationship('ChallengeFlag', backref='unlocks')
    
    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('user_id', 'team_id', 'challenge_id', name='unique_unlock'),
    )
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'team_id': self.team_id,
            'challenge_id': self.challenge_id,
            'unlocked_by_flag_id': self.unlocked_by_flag_id,
            'unlocked_at': self.unlocked_at.isoformat() if self.unlocked_at else None
        }
    
    def __repr__(self):
        return f'<ChallengeUnlock Challenge:{self.challenge_id} by Flag:{self.unlocked_by_flag_id}>'
