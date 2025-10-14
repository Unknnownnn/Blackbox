import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, send_from_directory, abort
from flask_login import LoginManager
from flask.json.provider import DefaultJSONProvider
from config import config
from models import db
from models.user import User
from services.cache import cache_service
from services.websocket import WebSocketService, socketio
from services.file_storage import file_storage
import os
from decimal import Decimal

class DecimalJSONProvider(DefaultJSONProvider):
    """Custom JSON provider to handle Decimal objects"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super().default(obj)

def create_app(config_name=None):
    """Create and configure the Flask application"""
    
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Set custom JSON provider
    app.json = DecimalJSONProvider(app)
    
    # Initialize extensions
    db.init_app(app)
    cache_service.init_app(app)
    WebSocketService.init_app(app)
    file_storage.init_app(app)
    
    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Register blueprints
    from routes.auth import auth_bp
    from routes.challenges import challenges_bp
    from routes.teams import teams_bp
    from routes.scoreboard import scoreboard_bp
    from routes.admin import admin_bp
    from routes.setup import setup_bp
    from routes.hints import hints_bp
    
    app.register_blueprint(setup_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(challenges_bp)
    app.register_blueprint(teams_bp)
    app.register_blueprint(scoreboard_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(hints_bp)
    
    # Setup check middleware
    @app.before_request
    def check_setup():
        """Redirect to setup if no admin exists"""
        from flask import request
        from routes.setup import is_setup_complete
        
        # Skip setup check for these paths
        if request.path.startswith('/setup') or \
           request.path.startswith('/static') or \
           request.path.startswith('/health') or \
           request.path.startswith('/files'):
            return None
        
        # Check if setup is complete
        try:
            if not is_setup_complete():
                from flask import redirect, url_for
                return redirect(url_for('setup.initial_setup'))
        except:
            # Database might not be initialized yet
            pass
        
        return None
    
    # Main routes
    @app.route('/')
    def index():
        """Homepage"""
        return render_template('index.html')
    
    @app.route('/about')
    def about():
        """About page"""
        return render_template('about.html')
    
    @app.route('/health')
    def health():
        """Health check endpoint"""
        return {'status': 'healthy', 'service': 'ctf-platform'}, 200
    
    # File serving route
    @app.route('/files/<path:filename>')
    def serve_file(filename):
        """Serve uploaded files with original filename"""
        from models.file import ChallengeFile
        
        upload_folder = app.config.get('UPLOAD_FOLDER', 'uploads')
        
        # Try to find the file in the database to get original filename
        file_record = ChallengeFile.query.filter_by(relative_path=filename.replace('/', os.sep)).first()
        
        try:
            if file_record:
                # Serve with original filename
                return send_from_directory(
                    upload_folder, 
                    filename,
                    as_attachment=True,
                    download_name=file_record.original_filename
                )
            else:
                # Fallback: serve file as-is
                return send_from_directory(upload_folder, filename, as_attachment=True)
        except FileNotFoundError:
            abort(404)
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500
    
    # Template context processors
    @app.context_processor
    def inject_config():
        """Inject configuration into all templates"""
        return {
            'ctf_name': app.config.get('CTF_NAME', 'CTF Platform'),
            'ctf_description': app.config.get('CTF_DESCRIPTION', ''),
            'registration_enabled': app.config.get('REGISTRATION_ENABLED', True)
        }
    
    return app


def main():
    """Main entry point"""
    app = create_app()
    
    # Run with SocketIO
    socketio.run(
        app,
        host=app.config.get('HOST', '0.0.0.0'),
        port=app.config.get('PORT', 5000),
        debug=app.config.get('DEBUG', True),
        use_reloader=True
    )


# For Gunicorn with eventlet worker
app = create_app()


if __name__ == '__main__':
    main()
