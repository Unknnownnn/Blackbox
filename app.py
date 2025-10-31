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
    from routes.notifications import notifications_bp
    from routes.setup import setup_bp
    from routes.hints import hints_bp
    from routes.container import container_bp
    
    app.register_blueprint(setup_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(challenges_bp)
    app.register_blueprint(teams_bp)
    app.register_blueprint(scoreboard_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(hints_bp)
    app.register_blueprint(container_bp)
    
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
        except Exception as e:
            # Database might not be initialized yet or connection lost
            app.logger.error(f"Setup check failed: {e}")
            try:
                db.session.rollback()
                db.session.remove()
            except:
                pass
        
        return None
    
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        """Remove database session at end of request"""
        try:
            if exception:
                db.session.rollback()
            db.session.remove()
        except Exception as e:
            app.logger.error(f"Error during session cleanup: {e}")
    
    # Main routes
    @app.route('/')
    def index():
        """Homepage"""
        return render_template('index.html')
    
    @app.route('/about')
    def about():
        """About page"""
        return render_template('about.html')
    
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
        import os
        from urllib.parse import quote
        
        upload_folder = app.config.get('UPLOAD_FOLDER', 'uploads')
        
        # Normalize the path for database lookup (try both forward and backslashes)
        normalized_path = filename.replace('/', os.sep)
        
        # Try to find file record (check both path formats)
        file_record = ChallengeFile.query.filter_by(relative_path=normalized_path).first()
        if not file_record:
            # Try with forward slashes  
            file_record = ChallengeFile.query.filter_by(relative_path=filename).first()
        
        # Build full file path
        file_path = os.path.join(upload_folder, normalized_path)
        
        if not os.path.exists(file_path):
            app.logger.warning(f"File not found: {file_path}")
            abort(404)
        
        # Determine the filename to use for download
        if file_record and file_record.original_filename:
            download_filename = file_record.original_filename
            app.logger.info(f"Found DB record: {download_filename}")
        else:
            download_filename = os.path.basename(file_path)
            app.logger.warning(f"No DB record, using: {download_filename}")
        
        # Use send_file with proper parameters
        return send_file(
            file_path,
            as_attachment=True,
            download_name=download_filename,
            mimetype=file_record.mime_type if file_record and file_record.mime_type else 'application/octet-stream'
        )
    
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
            # Check database connectivity with timeout
            from sqlalchemy import text
            db.session.execute(text('SELECT 1'))
            db.session.commit()
            db_status = 'healthy'
        except Exception as e:
            app.logger.error(f"Database health check failed: {e}")
            # Try to recover connection
            try:
                db.session.rollback()
                db.session.remove()
            except:
                pass
            db_status = f'unhealthy: {str(e)[:100]}'
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
    
    @app.template_filter('format_datetime')
    def format_datetime_filter(dt, format_str='%Y-%m-%d %H:%M:%S'):
        """Template filter to format datetime in platform timezone"""
        from utils.timezone import format_datetime
        return format_datetime(dt, format_str)
    
    @app.template_filter('to_platform_tz')
    def to_platform_tz_filter(dt):
        """Template filter to convert datetime to platform timezone"""
        from utils.timezone import convert_to_platform_tz
        return convert_to_platform_tz(dt)
    
    return app


def main():
    """Main entry point"""
    app = create_app()
    
    # Initialize backup scheduler after app is created
    with app.app_context():
        try:
            from services.backup_scheduler import init_backup_scheduler
            scheduler = init_backup_scheduler(app)
            # Trigger initial schedule setup
            scheduler.reschedule()
        except Exception as e:
            app.logger.warning(f"Could not initialize backup scheduler: {e}")
    
    socketio.run(
        app,
        host=app.config.get('HOST', '0.0.0.0'),
        port=app.config.get('PORT', 5000),
        debug=app.config.get('DEBUG', True),
        use_reloader=True
    )


app = create_app()

# Initialize backup scheduler for production (gunicorn)
with app.app_context():
    try:
        from services.backup_scheduler import init_backup_scheduler
        scheduler = init_backup_scheduler(app)
        scheduler.reschedule()
    except Exception as e:
        app.logger.warning(f"Could not initialize backup scheduler during app creation: {e}")

    # Ensure DB schema has required docker-related columns and defaults
    try:
        from scripts.db_schema import ensure_docker_schema
        ensure_docker_schema()
        app.logger.info("Ensured docker DB schema and defaults")
    except Exception as e:
        app.logger.warning(f"Could not ensure docker DB schema on startup: {e}")

# Initialize container reconciliation background task
try:
    import threading
    from services.container_reconciliation import run_reconciliation_loop
    
    reconciliation_thread = threading.Thread(
        target=run_reconciliation_loop,
        args=(app, 60),  # Check every 60 seconds
        daemon=True,
        name="ContainerReconciliation"
    )
    reconciliation_thread.start()
    app.logger.info("Container reconciliation background task started")
except Exception as e:
    app.logger.warning(f"Could not start container reconciliation task: {e}")


if __name__ == '__main__':
    main()
