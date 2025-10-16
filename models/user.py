from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from models import db

class User(UserMixin, db.Model):
    """User model for authentication and profile"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # User info
    full_name = db.Column(db.String(120))
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    
    # Team relationship - nullable to break circular dependency
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id', use_alter=True, name='fk_user_team'), nullable=True)
    is_team_captain = db.Column(db.Boolean, default=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Relationships
    submissions = db.relationship('Submission', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    solves = db.relationship('Solve', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if password matches hash"""
        return check_password_hash(self.password_hash, password)
    
    def get_team(self):
        """Get user's team"""
        from models.team import Team
        return Team.query.get(self.team_id) if self.team_id else None
    
    def get_score(self):
        """Calculate user's total score dynamically (solves - hint costs)
        
        For dynamic challenges: Recalculates based on current challenge value
        For static challenges: Uses stored points_earned
        """
        if self.team_id:
            team = self.get_team()
            return team.get_score() if team else 0
        else:
            # Sum solve points (recalculated for dynamic challenges)
            solve_points = sum([solve.get_current_points() for solve in self.solves])
            
            # Subtract hint costs
            from models.hint import HintUnlock
            hint_costs = db.session.query(db.func.sum(HintUnlock.cost_paid)).filter(
                HintUnlock.user_id == self.id,
                HintUnlock.team_id == None
            ).scalar() or 0
            
            # Convert Decimal to int for JSON serialization
            total = int(solve_points) - int(hint_costs)
            return total
    
    def get_solves_count(self):
        """Get number of challenges solved"""
        return self.solves.count()
    
    def has_solved(self, challenge_id):
        """Check if user has solved a challenge"""
        return self.solves.filter_by(challenge_id=challenge_id).first() is not None
    
    def to_dict(self, include_email=False):
        """Convert user to dictionary"""
        data = {
            'id': self.id,
            'username': self.username,
            'full_name': self.full_name,
            'is_admin': self.is_admin,
            'team_id': self.team_id,
            'is_team_captain': self.is_team_captain,
            'score': self.get_score(),
            'solves': self.get_solves_count(),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        if include_email:
            data['email'] = self.email
        return data
    
    def __repr__(self):
        return f'<User {self.username}>'
