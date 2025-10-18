from datetime import datetime
from models import db, team_members

class Team(db.Model):
    """Team model for collaborative play"""
    __tablename__ = 'teams'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    invite_code = db.Column(db.String(8), unique=True, nullable=False, index=True)  # Unique invite code
    password_hash = db.Column(db.String(255), nullable=True)  # Optional team password (deprecated)
    
    # Team info
    affiliation = db.Column(db.String(120))  # Organization/School
    country = db.Column(db.String(50))
    website = db.Column(db.String(200))
    is_active = db.Column(db.Boolean, default=True)
    
    # Captain - nullable to break circular dependency with users table
    captain_id = db.Column(db.Integer, db.ForeignKey('users.id', use_alter=True, name='fk_team_captain'), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    members = db.relationship('User', backref='team', lazy='dynamic', 
                            foreign_keys='User.team_id')
    solves = db.relationship('Solve', backref='team', lazy='dynamic', cascade='all, delete-orphan')
    
    def get_score(self):
        """Calculate team's total score dynamically (solves - hint costs)
        
        For dynamic challenges: Recalculates based on current challenge value
        For static challenges: Uses stored points_earned
        """
        # Sum solve points (recalculated for dynamic challenges)
        solve_points = sum([solve.get_current_points() for solve in self.solves])
        
        # Subtract hint costs
        from models.hint import HintUnlock
        hint_costs = db.session.query(db.func.sum(HintUnlock.cost_paid)).filter(
            HintUnlock.team_id == self.id
        ).scalar() or 0
        
        # Convert Decimal to int for JSON serialization
        total = int(solve_points) - int(hint_costs)
        return total
    
    def get_solves_count(self):
        """Get number of challenges solved by team (excludes manual adjustments)"""
        return self.solves.filter(db.text('challenge_id IS NOT NULL')).count()
    
    def get_members(self):
        """Get all team members"""
        from models.user import User
        return User.query.filter_by(team_id=self.id).all()
    
    def get_member_count(self):
        """Get number of team members"""
        return self.members.count()
    
    def has_solved(self, challenge_id):
        """Check if team has solved a challenge"""
        return self.solves.filter_by(challenge_id=challenge_id).first() is not None
    
    def get_last_solve_time(self):
        """Get the timestamp of the last solve"""
        last_solve = self.solves.order_by(Solve.solved_at.desc()).first()
        return last_solve.solved_at if last_solve else None
    
    def can_join(self, max_size=4):
        """Check if team has space for new members"""
        return self.get_member_count() < max_size
    
    def set_password(self, password):
        """Hash and set team password"""
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password) if password else None
    
    def check_password(self, password):
        """Check if password matches hash"""
        from werkzeug.security import check_password_hash
        if not self.password_hash:
            return True  # No password set
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self, include_members=False, include_invite_code=False):
        """Convert team to dictionary"""
        data = {
            'id': self.id,
            'name': self.name,
            'affiliation': self.affiliation,
            'country': self.country,
            'website': self.website,
            'captain_id': self.captain_id,
            'score': self.get_score(),
            'solves': self.get_solves_count(),
            'member_count': self.get_member_count(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'has_password': bool(self.password_hash)
        }
        if include_invite_code:
            data['invite_code'] = self.invite_code
        if include_members:
            data['members'] = [m.to_dict() for m in self.get_members()]
        return data
    
    @staticmethod
    def generate_invite_code():
        """Generate a unique 8-character invite code"""
        import string
        import random
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            if not Team.query.filter_by(invite_code=code).first():
                return code
    
    def __repr__(self):
        return f'<Team {self.name}>'


# Import Solve here to avoid circular import
from models.submission import Solve
