import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, send_from_directory, send_file, abort
from flask_login import LoginManager
from flask.json.provider import DefaultJSONProvider
from config import config
from models import db
from models.user import User
from services.cache import cache_service
from services.websocket import WebSocketService, socketio
from services.file_storage import file_storage
from security_utils import init_security
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
    
    # Explicitly set static folder path
    static_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    
    app = Flask(__name__, static_folder=static_folder, static_url_path='/static')
    app.config.from_object(config[config_name])
    
    # Set custom JSON provider
    app.json = DecimalJSONProvider(app)
    
    # Initialize extensions
    db.init_app(app)
    cache_service.init_app(app)
    WebSocketService.init_app(app)
    file_storage.init_app(app)
    
    # Initialize security features (CSRF, security headers, etc.)
    init_security(app)
    
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
        return {'status': 'healthy', 'service': 'blackbox-ctf'}, 200
    
    @app.route('/uploads/<path:filename>')
    def serve_logo(filename):
        """Serve uploaded logo files from /var/uploads/logos"""
        logos_folder = '/var/uploads/logos'
        try:
            return send_from_directory(logos_folder, filename)
        except FileNotFoundError:
            abort(404)
    
    @app.route('/files/<path:filename>')
    def serve_file(filename):
        """Serve uploaded files with original filename"""
        from models.file import ChallengeFile
        from flask import Response
        import os
        from werkzeug.utils import safe_join
        
        upload_folder = app.config.get('UPLOAD_FOLDER', 'uploads')
        
        # Normalize the path for database lookup (try both forward and backslashes)
        normalized_path = filename.replace('/', os.sep)
        
        # Try to find file record (check both path formats)
        file_record = ChallengeFile.query.filter_by(relative_path=normalized_path).first()
        if not file_record:
            # Try with forward slashes
            file_record = ChallengeFile.query.filter_by(relative_path=filename).first()
        
        # Build full file path safely
        file_path = safe_join(upload_folder, normalized_path)
        
        if not file_path or not os.path.exists(file_path):
            app.logger.warning(f"File not found: {file_path}")
            abort(404)
        
        # Determine the filename to use for download
        download_filename = file_record.original_filename if file_record and file_record.original_filename else os.path.basename(file_path)
        
        # Read file content
        with open(file_path, 'rb') as f:
            file_data = f.read()
        
        # Create response with proper headers for download
        response = Response(file_data)
        response.headers['Content-Disposition'] = f'attachment; filename="{download_filename}"'
        
        # Set content type if available
        if file_record and hasattr(file_record, 'mime_type') and file_record.mime_type:
            response.headers['Content-Type'] = file_record.mime_type
        else:
            response.headers['Content-Type'] = 'application/octet-stream'
        
        app.logger.info(f"Serving file: {download_filename} (stored as: {filename})")
        
        return response
    
    @app.route('/favicon.ico')
    def favicon():
        """Serve favicon"""
        return send_from_directory(
            os.path.join(app.root_path, 'static'),
            'favicon.ico',
            mimetype='image/vnd.microsoft.icon'
        )
    
    @app.errorhandler(404)
    def not_found(error):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500
    
    @app.route('/health')
    def health_check():
        """Health check endpoint for load balancers and monitoring"""
        from datetime import datetime
        try:
            # Check database connectivity
            db.session.execute(db.text('SELECT 1'))
            db_status = 'healthy'
        except Exception as e:
            db_status = f'unhealthy: {str(e)}'
        
        try:
            # Check Redis connectivity
            cache_service.redis_client.ping()
            redis_status = 'healthy'
        except Exception as e:
            redis_status = f'unhealthy: {str(e)}'
        
        # Overall health
        is_healthy = db_status == 'healthy' and redis_status == 'healthy'
        
        health_data = {
            'status': 'healthy' if is_healthy else 'unhealthy',
            'timestamp': datetime.utcnow().isoformat(),
            'checks': {
                'database': db_status,
                'redis': redis_status
            },
            'config': {
                'workers': os.getenv('WORKERS', '1'),
                'worker_class': os.getenv('WORKER_CLASS', 'eventlet')
            }
        }
        
        status_code = 200 if is_healthy else 503
        return app.json.response(**health_data), status_code
    
    @app.context_processor
    def inject_config():
        """Inject configuration into all templates"""
        from models.settings import Settings
        
        # Load from database settings (with fallback to config)
        ctf_name = Settings.get('ctf_name', app.config.get('CTF_NAME', 'BlackBox CTF'))
        ctf_description = Settings.get('ctf_description', app.config.get('CTF_DESCRIPTION', ''))
        allow_registration = Settings.get('allow_registration', True)
        ctf_logo = Settings.get('ctf_logo', '')
        teams_enabled = Settings.get('teams_enabled', True, type='bool')
        scoreboard_visible = Settings.get('scoreboard_visible', True, type='bool')
        
        return {
            'ctf_name': ctf_name,
            'ctf_description': ctf_description,
            'registration_enabled': allow_registration,
            'ctf_logo': ctf_logo,
            'teams_enabled': teams_enabled,
            'scoreboard_visible': scoreboard_visible,
            'settings': Settings
        }
    
    return app


def main():
    """Main entry point"""
    app = create_app()
    
    socketio.run(
        app,
        host=app.config.get('HOST', '0.0.0.0'),
        port=app.config.get('PORT', 5000),
        debug=app.config.get('DEBUG', True),
        use_reloader=True
    )


app = create_app()


if __name__ == '__main__':
    main()
