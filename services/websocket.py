from flask_socketio import SocketIO, emit, join_room, leave_room, rooms
from flask import request
from flask_login import current_user

socketio = SocketIO(cors_allowed_origins="*", async_mode='eventlet')

class WebSocketService:
    """Service for managing WebSocket connections and real-time updates"""
    
    @staticmethod
    def init_app(app):
        """Initialize SocketIO with Flask app"""
        socketio.init_app(app, 
                         cors_allowed_origins="*",
                         async_mode='eventlet',
                         logger=True,
                         engineio_logger=True)
    
    @staticmethod
    def emit_scoreboard_update(scoreboard_data):
        """Emit scoreboard update to all connected clients"""
        socketio.emit('scoreboard_update', scoreboard_data, namespace='/live')
    
    @staticmethod
    def emit_new_solve(solve_data):
        """Emit new solve notification"""
        socketio.emit('new_solve', solve_data, namespace='/live')
    
    @staticmethod
    def emit_challenge_update(challenge_data):
        """Emit challenge update (points change)"""
        socketio.emit('challenge_update', challenge_data, namespace='/live')


# WebSocket event handlers
@socketio.on('connect', namespace='/live')
def handle_connect():
    """Handle client connection"""
    print(f'Client connected: {request.sid}')
    emit('connected', {'data': 'Connected to live updates'})


@socketio.on('disconnect', namespace='/live')
def handle_disconnect():
    """Handle client disconnection"""
    print(f'Client disconnected: {request.sid}')


@socketio.on('join_scoreboard', namespace='/live')
def handle_join_scoreboard():
    """Client joins scoreboard room for live updates"""
    join_room('scoreboard')
    emit('status', {'msg': 'Joined scoreboard room'})


@socketio.on('leave_scoreboard', namespace='/live')
def handle_leave_scoreboard():
    """Client leaves scoreboard room"""
    leave_room('scoreboard')
    emit('status', {'msg': 'Left scoreboard room'})


@socketio.on('request_scoreboard', namespace='/live')
def handle_request_scoreboard():
    """Client requests current scoreboard data"""
    from services.scoring import ScoringService
    from services.cache import cache_service
    from models.settings import Settings
    
    # Check if teams are enabled
    teams_enabled = Settings.get('teams_enabled', default=True, type='bool')
    
    # Try cache first
    cache_key = 'scoreboard_team' if teams_enabled else 'scoreboard_individual'
    scoreboard = cache_service.get(cache_key)
    
    if not scoreboard:
        # Generate fresh scoreboard
        scoreboard = ScoringService.get_scoreboard(team_based=teams_enabled, limit=100)
        cache_service.set(cache_key, scoreboard, ttl=60)
    
    emit('scoreboard_update', scoreboard)


@socketio.on('ping', namespace='/live')
def handle_ping():
    """Handle ping from client"""
    emit('pong', {'timestamp': str(__import__('datetime').datetime.utcnow())})
