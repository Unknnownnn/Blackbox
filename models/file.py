from models import db
from datetime import datetime

class ChallengeFile(db.Model):
    """Model for tracking challenge files"""
    __tablename__ = 'challenge_files'
    
    id = db.Column(db.Integer, primary_key=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey('challenges.id'), nullable=False, index=True)
    
    # File information
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    filepath = db.Column(db.String(512), nullable=False)
    relative_path = db.Column(db.String(512), nullable=False)
    
    # File metadata
    file_hash = db.Column(db.String(64))  # SHA256 hash
    file_size = db.Column(db.Integer)  # Size in bytes
    mime_type = db.Column(db.String(100))
    
    # Timestamps
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationship
    challenge = db.relationship('Challenge', backref=db.backref('files_list', lazy='dynamic', cascade='all, delete-orphan'))
    
    def get_download_url(self):
        """Get the download URL for this file"""
        # Avoid using backslashes inside f-strings (which causes a SyntaxError)
        cleaned = self.relative_path.replace('\\', '/') if self.relative_path else ''
        return '/files/' + cleaned
    
    def format_size(self):
        """Format file size in human-readable format"""
        if not self.file_size:
            return "Unknown"
        
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"
    
    def to_dict(self):
        """Convert file to dictionary"""
        return {
            'id': self.id,
            'challenge_id': self.challenge_id,
            'original_filename': self.original_filename,
            'stored_filename': self.stored_filename,
            'download_url': self.get_download_url(),
            'file_hash': self.file_hash,
            'file_size': self.file_size,
            'size_formatted': self.format_size(),
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None
        }
    
    def __repr__(self):
        return f'<ChallengeFile {self.original_filename}>'
