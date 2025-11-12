from datetime import datetime
from models import db

class ContainerInstance(db.Model):
    """Model for tracking active container instances"""
    __tablename__ = 'container_instances'
    
    id = db.Column(db.Integer, primary_key=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey('challenges.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=True)
    
    # Docker container details
    container_id = db.Column(db.String(128), nullable=False, unique=True)
    container_name = db.Column(db.String(256), nullable=False)
    docker_image = db.Column(db.String(256), nullable=False)
    
    # Network details
    port = db.Column(db.Integer, nullable=False)
    host_ip = db.Column(db.String(256), nullable=True)  # Docker host IP
    host_port = db.Column(db.Integer, nullable=True)  # Mapped host port
    ip_address = db.Column(db.String(45), nullable=True)  # Container IP address
    docker_info = db.Column(db.JSON, nullable=True)  # Additional Docker metadata
    
    # State tracking
    status = db.Column(db.String(20), default='starting')  # starting, running, stopping, stopped, error
    session_id = db.Column(db.String(64), nullable=False, unique=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    started_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    last_revert_time = db.Column(db.DateTime, nullable=True)
    
    # Error tracking
    error_message = db.Column(db.Text, nullable=True)
    
    # Dynamic flag storage (unique per-team, per-challenge, per-instance)
    dynamic_flag = db.Column(db.String(512), nullable=True)
    
    # Relationships
    challenge = db.relationship('Challenge', backref='container_instances')
    user = db.relationship('User', backref='container_instances')
    team = db.relationship('Team', backref='container_instances')
    
    def __repr__(self):
        return f'<ContainerInstance {self.container_name} (user={self.user_id}, challenge={self.challenge_id})>'
    
    def to_dict(self):
        """Convert instance to dictionary"""
        # Build connection info if we have challenge data
        connection_info = None
        if self.challenge and self.challenge.docker_connection_info:
            connection_info = self.challenge.docker_connection_info.replace(
                '{host}', self.host_ip or 'localhost'
            ).replace(
                '{port}', str(self.host_port) if self.host_port else ''
            )
        
        # Calculate expires_at in milliseconds since epoch for JS to use (avoids timezone confusion)
        expires_at_ms = None
        if self.expires_at:
            expires_at_ms = int(self.expires_at.timestamp() * 1000)
        
        return {
            'id': self.id,
            'challenge_id': self.challenge_id,
            'user_id': self.user_id,
            'team_id': self.team_id,
            'container_id': self.container_id,
            'container_name': self.container_name,
            'docker_image': self.docker_image,
            'port': self.port,
            'host_ip': self.host_ip,
            'host_port': self.host_port,
            'ip_address': self.ip_address,
            'status': self.status,
            'session_id': self.session_id,
            'connection_info': connection_info,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'expires_at_ms': expires_at_ms,  # Milliseconds since epoch for JS countdown
            'last_revert_time': self.last_revert_time.isoformat() if self.last_revert_time else None,
            'error_message': self.error_message
        }
    
    def is_expired(self):
        """Check if container has expired"""
        return datetime.utcnow() > self.expires_at
    
    def is_active(self):
        """Check if container is in an active state"""
        return self.status in ['starting', 'running']
    
    def get_remaining_time(self):
        """Get remaining time in human-readable format"""
        if not self.expires_at:
            return 'N/A'
        
        now = datetime.utcnow()
        if now >= self.expires_at:
            return 'Expired'
        
        delta = self.expires_at - now
        
        # Calculate hours, minutes, seconds
        total_seconds = int(delta.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        # Format based on time remaining
        if hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    
    def get_expected_flag(self):
        """Get the expected dynamic flag for this container from cache or DB"""
        from services.cache import cache_service
        
        # First try DB column
        if self.dynamic_flag:
            return self.dynamic_flag
        
        # Fallback to cache (legacy)
        cache_key = f"dynamic_flag:{self.session_id}"
        cached_flag = cache_service.get(cache_key)
        if cached_flag:
            return cached_flag
        
        # Try mapping cache (team-based)
        if self.team_id:
            team_part = f'team_{self.team_id}'
        else:
            team_part = f'user_{self.id}'
        
        mapping_key = f"dynamic_flag_mapping:{self.challenge_id}:{team_part}"
        mapped_flag = cache_service.get(mapping_key)
        return mapped_flag
    
    def verify_flag(self, submitted_flag):
        """Verify if submitted flag matches this container's expected flag"""
        expected = self.get_expected_flag()
        if not expected:
            return {'valid': False, 'reason': 'No dynamic flag generated for this container'}
        
        # Check case-sensitive match
        if submitted_flag == expected:
            return {'valid': True, 'expected': expected}
        
        # Check case-insensitive if challenge allows
        if self.challenge and not getattr(self.challenge, 'flag_case_sensitive', True):
            if submitted_flag.lower() == expected.lower():
                return {'valid': True, 'expected': expected, 'note': 'Case-insensitive match'}
        
        return {'valid': False, 'expected': expected, 'submitted': submitted_flag}


class ContainerEvent(db.Model):
    """Model for logging container lifecycle events"""
    __tablename__ = 'container_events'
    
    id = db.Column(db.Integer, primary_key=True)
    container_instance_id = db.Column(db.Integer, db.ForeignKey('container_instances.id'), nullable=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey('challenges.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Event details
    event_type = db.Column(db.String(50), nullable=False)  # start, stop, revert, expire, error
    status = db.Column(db.String(20), nullable=False)  # success, failure, pending
    message = db.Column(db.Text, nullable=True)
    
    # Metadata
    ip_address = db.Column(db.String(45), nullable=True)
    container_id = db.Column(db.String(128), nullable=True)
    
    # Timestamp
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    container_instance = db.relationship('ContainerInstance', backref='events')
    challenge = db.relationship('Challenge', backref='container_events')
    user = db.relationship('User', backref='container_events')
    
    def __repr__(self):
        return f'<ContainerEvent {self.event_type} (user={self.user_id}, challenge={self.challenge_id})>'
    
    def to_dict(self):
        """Convert event to dictionary"""
        return {
            'id': self.id,
            'container_instance_id': self.container_instance_id,
            'challenge_id': self.challenge_id,
            'user_id': self.user_id,
            'event_type': self.event_type,
            'status': self.status,
            'message': self.message,
            'ip_address': self.ip_address,
            'container_id': self.container_id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }
