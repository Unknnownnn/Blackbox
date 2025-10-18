from datetime import datetime
from models import db

class Hint(db.Model):
    """Hint model for challenge hints with costs"""
    __tablename__ = 'hints'
    
    id = db.Column(db.Integer, primary_key=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey('challenges.id', ondelete='CASCADE'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    cost = db.Column(db.Integer, nullable=False, default=0)  # Points cost to unlock hint
    order = db.Column(db.Integer, nullable=False, default=0)  # Display order
    
    # Prerequisite hint - must unlock this hint before unlocking the current one
    requires_hint_id = db.Column(db.Integer, db.ForeignKey('hints.id', ondelete='SET NULL'), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    challenge = db.relationship('Challenge', backref=db.backref('hint_objects', lazy='dynamic', cascade='all, delete-orphan'))
    unlocks = db.relationship('HintUnlock', backref='hint', lazy='dynamic', cascade='all, delete-orphan')
    
    # Self-referential relationship for prerequisites
    prerequisite_hint = db.relationship('Hint', remote_side=[id], backref='dependent_hints', foreign_keys=[requires_hint_id])
    
    def is_unlocked_by_user(self, user_id):
        """Check if hint is unlocked by user"""
        return self.unlocks.filter_by(user_id=user_id).first() is not None
    
    def is_unlocked_by_team(self, team_id):
        """Check if hint is unlocked by team"""
        return self.unlocks.filter_by(team_id=team_id).first() is not None
    
    def can_unlock(self, user_id=None, team_id=None):
        """Check if user/team can unlock this hint (checks prerequisites)
        
        Args:
            user_id: User ID to check (for solo mode)
            team_id: Team ID to check (for team mode)
            
        Returns:
            tuple: (can_unlock: bool, reason: str or None)
        """
        # If no prerequisite, can always unlock (if not already unlocked)
        if not self.requires_hint_id:
            return (True, None)
        
        # Check if prerequisite hint is unlocked
        prerequisite = Hint.query.get(self.requires_hint_id)
        if not prerequisite:
            # Prerequisite was deleted, allow unlock
            return (True, None)
        
        if team_id:
            prereq_unlocked = prerequisite.is_unlocked_by_team(team_id)
        else:
            prereq_unlocked = prerequisite.is_unlocked_by_user(user_id)
        
        if not prereq_unlocked:
            return (False, f'You must unlock Hint #{prerequisite.order} first')
        
        return (True, None)
    
    def to_dict(self, include_content=False):
        """Convert hint to dictionary"""
        data = {
            'id': self.id,
            'challenge_id': self.challenge_id,
            'cost': self.cost,
            'order': self.order,
            'requires_hint_id': self.requires_hint_id,
        }
        
        if include_content:
            data['content'] = self.content
        
        return data
    
    def __repr__(self):
        return f'<Hint {self.id} for Challenge {self.challenge_id}>'


class HintUnlock(db.Model):
    """Track which hints have been unlocked by which users/teams"""
    __tablename__ = 'hint_unlocks'
    
    id = db.Column(db.Integer, primary_key=True)
    hint_id = db.Column(db.Integer, db.ForeignKey('hints.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id', ondelete='CASCADE'), nullable=True)
    cost_paid = db.Column(db.Integer, nullable=False)  # Points deducted when unlocked
    
    # Timestamps
    unlocked_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('hint_unlocks', lazy='dynamic'))
    team = db.relationship('Team', backref=db.backref('hint_unlocks', lazy='dynamic'))
    
    def __repr__(self):
        return f'<HintUnlock {self.hint_id} by User {self.user_id}>'
