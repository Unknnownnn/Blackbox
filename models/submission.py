from datetime import datetime
from models import db

class Submission(db.Model):
    """Submission model for tracking all flag attempts"""
    __tablename__ = 'submissions'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Relationships
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey('challenges.id'), nullable=False, index=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=True, index=True)
    
    # Submission details
    submitted_flag = db.Column(db.String(255), nullable=False)
    is_correct = db.Column(db.Boolean, default=False, index=True)
    ip_address = db.Column(db.String(45))  # IPv6 compatible
    
    # Timestamp
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def to_dict(self):
        """Convert submission to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'challenge_id': self.challenge_id,
            'team_id': self.team_id,
            'is_correct': self.is_correct,
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None
        }
    
    def __repr__(self):
        return f'<Submission {self.id} - User:{self.user_id} Challenge:{self.challenge_id}>'


class Solve(db.Model):
    """Solve model for tracking successful challenge completions
    
    NOTE: For dynamic scoring, points_earned stores the value at solve time,
    but actual score is recalculated from current challenge value.
    For static scoring, points_earned is used directly.
    For manual adjustments, challenge_id is None and points_earned is used.
    """
    __tablename__ = 'solves'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Relationships
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey('challenges.id'), nullable=True, index=True)  # None for manual adjustments
    flag_id = db.Column(db.Integer, db.ForeignKey('challenge_flags.id'), nullable=True)  # Which flag was used
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=True, index=True)
    
    # Solve details
    points_earned = db.Column(db.Integer, nullable=False)  # Points at time of solve (for reference/manual adjustments)
    solve_time = db.Column(db.Integer)  # Time taken in seconds (if tracked)
    is_first_blood = db.Column(db.Boolean, default=False)  # First solve of this challenge
    
    # Timestamp
    solved_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Unique constraint: one solve per user/team per challenge
    __table_args__ = (
        db.UniqueConstraint('user_id', 'challenge_id', name='unique_user_challenge'),
        db.UniqueConstraint('team_id', 'challenge_id', name='unique_team_challenge'),
    )
    
    def get_current_points(self):
        """Get current point value for this solve
        
        For dynamic challenges: Recalculate based on current challenge value
        For static challenges: Use stored points_earned
        For manual adjustments (challenge_id=None): Use stored points_earned
        """
        if self.challenge_id is None:
            # Manual adjustment - use stored value
            return self.points_earned
        
        from models.challenge import Challenge
        challenge = Challenge.query.get(self.challenge_id)
        
        if not challenge:
            # Challenge deleted - use stored value
            return self.points_earned
        
        if not challenge.is_dynamic:
            # Static challenge - use stored value
            return self.points_earned
        
        # Dynamic challenge - recalculate based on current value
        from services.scoring import ScoringService
        current_points = ScoringService.calculate_dynamic_points(challenge)
        
        # Add first blood bonus if enabled
        if self.is_first_blood:
            from models.settings import Settings
            first_blood_bonus = Settings.get('first_blood_bonus', 0, type='int')
            current_points += first_blood_bonus
        
        return current_points
    
    def to_dict(self):
        """Convert solve to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'challenge_id': self.challenge_id,
            'team_id': self.team_id,
            'points_earned': self.points_earned,
            'solved_at': self.solved_at.isoformat() if self.solved_at else None
        }
    
    def __repr__(self):
        return f'<Solve {self.id} - User:{self.user_id} Challenge:{self.challenge_id}>'
