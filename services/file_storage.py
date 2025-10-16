import os
import uuid
import hashlib
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import current_app
import shutil

class FileStorageService:
    """Service for managing file uploads and storage (similar to CTFd)"""
    
    # No file type restrictions - allow all file types
    
    def __init__(self, app=None):
        self.upload_folder = None
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize file storage with Flask app"""
        self.upload_folder = app.config.get('UPLOAD_FOLDER', 'uploads')
        
        # Create upload directory if it doesn't exist
        if not os.path.exists(self.upload_folder):
            os.makedirs(self.upload_folder)
        
        # Create subdirectories for organization
        subdirs = ['challenges', 'temp', 'avatars']
        for subdir in subdirs:
            path = os.path.join(self.upload_folder, subdir)
            if not os.path.exists(path):
                os.makedirs(path)
    
    def allowed_file(self, filename):
        """Check if file has a filename (always returns True - no restrictions)"""
        return filename and filename != ''
    
    def generate_unique_filename(self, original_filename):
        """Generate a unique filename while preserving extension"""
        # Get file extension (if any)
        ext = ''
        if '.' in original_filename:
            ext = '.' + original_filename.rsplit('.', 1)[1]
        
        # Generate unique ID
        unique_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        
        return f"{timestamp}_{unique_id}{ext}"
    
    def calculate_file_hash(self, filepath):
        """Calculate SHA256 hash of a file"""
        sha256_hash = hashlib.sha256()
        
        with open(filepath, "rb") as f:
            # Read file in chunks to handle large files
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        
        return sha256_hash.hexdigest()
    
    def save_challenge_file(self, file, challenge_id=None):
        """
        Save a challenge file
        
        Args:
            file: FileStorage object from request.files
            challenge_id: Optional challenge ID for organizing files
        
        Returns:
            dict with file information (filename, path, url, hash, size)
        """
        if not file or file.filename == '':
            return None
        
        if not self.allowed_file(file.filename):
            raise ValueError("Invalid filename")
        
        # Secure the original filename
        original_filename = secure_filename(file.filename)
        
        # Generate unique filename
        unique_filename = self.generate_unique_filename(original_filename)
        
        # Determine save path
        if challenge_id:
            challenge_dir = os.path.join(self.upload_folder, 'challenges', str(challenge_id))
            if not os.path.exists(challenge_dir):
                os.makedirs(challenge_dir)
            filepath = os.path.join(challenge_dir, unique_filename)
            relative_path = os.path.join('challenges', str(challenge_id), unique_filename)
        else:
            filepath = os.path.join(self.upload_folder, 'challenges', unique_filename)
            relative_path = os.path.join('challenges', unique_filename)
        
        # Save file
        file.save(filepath)
        
        # Calculate file hash and size
        file_hash = self.calculate_file_hash(filepath)
        file_size = os.path.getsize(filepath)
        
        return {
            'original_filename': original_filename,
            'stored_filename': unique_filename,
            'filepath': filepath,
            'relative_path': relative_path,
            'url': f"/files/{relative_path.replace(os.sep, '/')}",
            'hash': file_hash,
            'size': file_size,
            'uploaded_at': datetime.utcnow().isoformat()
        }
    
    def save_multiple_files(self, files, challenge_id=None):
        """
        Save multiple challenge files
        
        Args:
            files: List of FileStorage objects
            challenge_id: Optional challenge ID
        
        Returns:
            List of file information dictionaries
        """
        saved_files = []
        
        for file in files:
            try:
                file_info = self.save_challenge_file(file, challenge_id)
                if file_info:
                    saved_files.append(file_info)
            except Exception as e:
                print(f"Error saving file {file.filename}: {str(e)}")
                continue
        
        return saved_files
    
    def delete_file(self, filepath):
        """Delete a file from storage"""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                return True
        except Exception as e:
            print(f"Error deleting file {filepath}: {str(e)}")
        return False
    
    def delete_challenge_files(self, challenge_id):
        """Delete all files associated with a challenge"""
        challenge_dir = os.path.join(self.upload_folder, 'challenges', str(challenge_id))
        
        try:
            if os.path.exists(challenge_dir):
                shutil.rmtree(challenge_dir)
                return True
        except Exception as e:
            print(f"Error deleting challenge files: {str(e)}")
        return False
    
    def get_file_info(self, filepath):
        """Get information about a stored file"""
        if not os.path.exists(filepath):
            return None
        
        return {
            'exists': True,
            'size': os.path.getsize(filepath),
            'modified': datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat(),
            'hash': self.calculate_file_hash(filepath)
        }
    
    def format_file_size(self, size_bytes):
        """Format file size in human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"

# Global file storage service instance
file_storage = FileStorageService()
