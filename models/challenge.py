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
    images = db.Column(db.Text)  # JSON array of image URLs for display
    hints = db.Column(db.Text)  # JSON array of hints
    connection_info = db.Column(db.String(500))  # Connection info (nc host:port, URLs, etc.)
    
    # Docker container settings
    docker_enabled = db.Column(db.Boolean, default=False)
    docker_image = db.Column(db.String(256))  # Docker image:tag to use
    docker_connection_info = db.Column(db.String(512))  # Template with {host} {port} placeholders
    # Path inside container where the flag file should be written (e.g. /flag.txt)
    docker_flag_path = db.Column(db.String(256), nullable=True)
    
    # Scoring
    initial_points = db.Column(db.Integer, nullable=False, default=500)
    minimum_points = db.Column(db.Integer, nullable=False, default=50)
    decay_solves = db.Column(db.Integer, nullable=False, default=30)  # Solves for min points
    
    # Challenge state
    is_visible = db.Column(db.Boolean, default=True)
    is_hidden = db.Column(db.Boolean, default=False)  # Hidden until unlocked
    unlock_mode = db.Column(db.String(20), default='none')  # none, prerequisite, flag_unlock
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
        """Get number of solves (excludes manual adjustments)"""
        return self.solves.filter(db.text('challenge_id IS NOT NULL')).count()
    
    def get_submissions_count(self):
        """Get total number of submissions"""
        return self.submissions.count()
    
    def check_flag(self, submitted_flag, team_id=None, user_id=None):
        """Check if submitted flag is correct (checks all flags for this challenge)
        
        Args:
            submitted_flag: The flag string submitted by the user
            team_id: Optional team_id for dynamic flag validation
            user_id: Optional user_id for dynamic flag validation (when not in a team)
        
        Returns:
            Flag object if match found, True for legacy flags, or None if no match
        """
        from models.branching import ChallengeFlag
        from services.cache import cache_service
        
        # Get all flags for this challenge
        flags = ChallengeFlag.query.filter_by(challenge_id=self.id).all()
        
        # Check each flag
        for flag in flags:
            if flag.check_flag(submitted_flag):
                return flag  # Return the matching flag object
        
        # Check dynamic flags if docker is enabled
        if self.docker_enabled and (team_id or user_id):
            # Build the cache key for this team/user's dynamic flag
            if team_id:
                team_part = f'team_{team_id}'
            elif user_id:
                team_part = f'user_{user_id}'
            else:
                team_part = None
            
            if team_part:
                cache_key = f"dynamic_flag_mapping:{self.id}:{team_part}"
                expected_flag = cache_service.get(cache_key)
                
                if expected_flag and submitted_flag == expected_flag:
                    return True  # Dynamic flag matches
        
        # Legacy support: check old flag column if no flags defined
        if not flags and self.flag:
            if self.flag_case_sensitive:
                if submitted_flag == self.flag:
                    return True
            else:
                if submitted_flag.lower() == self.flag.lower():
                    return True
        
        return None
    
    def is_solved_by_user(self, user_id):
        """Check if challenge is solved by user"""
        return self.solves.filter_by(user_id=user_id).first() is not None
    
    def is_solved_by_team(self, team_id):
        """Check if challenge is solved by team"""
        return self.solves.filter_by(team_id=team_id).first() is not None
    
    def is_unlocked_for_user(self, user_id, team_id=None):
        """Check if challenge is unlocked for user/team based on prerequisites and flags"""
        from models.branching import ChallengePrerequisite, ChallengeUnlock
        
        # If not hidden or no unlock mode, it's always unlocked
        if not self.is_hidden or self.unlock_mode == 'none':
            return True
        
        # Check prerequisite mode
        if self.unlock_mode == 'prerequisite':
            # Check if all prerequisites are solved
            prerequisites = ChallengePrerequisite.query.filter_by(challenge_id=self.id).all()
            if not prerequisites:
                return True  # No prerequisites defined, so unlocked
            
            for prereq in prerequisites:
                # Check if prerequisite is solved by user or team
                if team_id:
                    if not prereq.prerequisite_challenge.is_solved_by_team(team_id):
                        return False
                else:
                    if not prereq.prerequisite_challenge.is_solved_by_user(user_id):
                        return False
            
            return True  # All prerequisites met
        
        # Check flag unlock mode
        if self.unlock_mode == 'flag_unlock':
            # Check if challenge was unlocked by a flag
            unlock = ChallengeUnlock.query.filter_by(
                user_id=user_id,
                team_id=team_id,
                challenge_id=self.id
            ).first()
            return unlock is not None
        
        return False
    
    def get_missing_prerequisites(self, user_id, team_id=None):
        """Get list of prerequisite challenges that are not yet solved"""
        from models.branching import ChallengePrerequisite
        
        if self.unlock_mode != 'prerequisite':
            return []
        
        prerequisites = ChallengePrerequisite.query.filter_by(challenge_id=self.id).all()
        missing = []
        
        for prereq in prerequisites:
            if team_id:
                if not prereq.prerequisite_challenge.is_solved_by_team(team_id):
                    missing.append(prereq.prerequisite_challenge)
            else:
                if not prereq.prerequisite_challenge.is_solved_by_user(user_id):
                    missing.append(prereq.prerequisite_challenge)
        
        return missing
    
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
            'connection_info': self.connection_info,
            'files': self.files,
            'hints': self.hints,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            # Docker fields
            'docker_enabled': self.docker_enabled,
            'docker_image': self.docker_image,
            'docker_connection_info': self.docker_connection_info,
            'docker_flag_path': self.docker_flag_path,
            'requires_team': self.requires_team
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
