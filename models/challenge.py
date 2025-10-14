from datetime import datetime
from models import db

class Challenge(db.Model):
    """Challenge model for CTF problems"""
    __tablename__ = 'challenges'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False, index=True)
    
    # Challenge content
    flag = db.Column(db.String(255), nullable=False)
    flag_case_sensitive = db.Column(db.Boolean, default=True)
    
    # Files and resources
    files = db.Column(db.Text)  # JSON array of file URLs
    hints = db.Column(db.Text)  # JSON array of hints
    
    # Scoring
    initial_points = db.Column(db.Integer, nullable=False, default=500)
    minimum_points = db.Column(db.Integer, nullable=False, default=50)
    decay_solves = db.Column(db.Integer, nullable=False, default=30)  # Solves for min points
    
    # Challenge state
    is_visible = db.Column(db.Boolean, default=True)
    is_enabled = db.Column(db.Boolean, default=True)  # Temporarily disable challenge
    is_dynamic = db.Column(db.Boolean, default=True)  # Use dynamic scoring
    requires_team = db.Column(db.Boolean, default=False)  # Require user to be in a team to solve
    
    # Metadata
    author = db.Column(db.String(100))
    difficulty = db.Column(db.String(20))  # easy, medium, hard
    max_attempts = db.Column(db.Integer, default=0)  # Max attempts per team/user (0=unlimited)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    submissions = db.relationship('Submission', backref='challenge', lazy='dynamic', 
                                cascade='all, delete-orphan')
    solves = db.relationship('Solve', backref='challenge', lazy='dynamic', 
                           cascade='all, delete-orphan')
    
    def get_current_points(self):
        """Calculate current points based on number of solves"""
        if not self.is_dynamic:
            return self.initial_points
        
        solve_count = self.solves.count()
        if solve_count == 0:
            return self.initial_points
        
        # Logarithmic decay function
        import math
        if solve_count >= self.decay_solves:
            return self.minimum_points
        
        # Calculate decay
        decay_rate = math.log(self.decay_solves) / (self.decay_solves - 1)
        points = self.initial_points - (self.initial_points - self.minimum_points) * \
                 (math.log(solve_count + 1) / math.log(self.decay_solves + 1))
        
        return max(int(points), self.minimum_points)
    
    def get_solves_count(self):
        """Get number of solves"""
        return self.solves.count()
    
    def get_submissions_count(self):
        """Get total number of submissions"""
        return self.submissions.count()
    
    def check_flag(self, submitted_flag):
        """Check if submitted flag is correct"""
        if self.flag_case_sensitive:
            return submitted_flag == self.flag
        else:
            return submitted_flag.lower() == self.flag.lower()
    
    def is_solved_by_user(self, user_id):
        """Check if challenge is solved by user"""
        return self.solves.filter_by(user_id=user_id).first() is not None
    
    def is_solved_by_team(self, team_id):
        """Check if challenge is solved by team"""
        return self.solves.filter_by(team_id=team_id).first() is not None
    
    def to_dict(self, include_flag=False, include_solves=True):
        """Convert challenge to dictionary"""
        data = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'points': self.get_current_points(),
            'initial_points': self.initial_points,
            'minimum_points': self.minimum_points,
            'is_visible': self.is_visible,
            'is_dynamic': self.is_dynamic,
            'author': self.author,
            'difficulty': self.difficulty,
            'files': self.files,
            'hints': self.hints,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        
        if include_solves:
            data['solves'] = self.get_solves_count()
            data['submissions'] = self.get_submissions_count()
        
        if include_flag:
            data['flag'] = self.flag
            data['flag_case_sensitive'] = self.flag_case_sensitive
        
        return data
    
    def __repr__(self):
        return f'<Challenge {self.name}>'
