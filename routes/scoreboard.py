from flask import Blueprint, render_template, jsonify
from flask_login import login_required
from services.scoring import ScoringService
from services.cache import cache_service

scoreboard_bp = Blueprint('scoreboard', __name__, url_prefix='/scoreboard')

@scoreboard_bp.route('/')
def view_scoreboard():
    """View scoreboard page"""
    return render_template('scoreboard.html')


@scoreboard_bp.route('/api/data')
def get_scoreboard_data():
    """Get scoreboard data (API endpoint)"""
    # Try cache first
    scoreboard = cache_service.get_scoreboard()
    
    if not scoreboard:
        # Generate fresh scoreboard
        scoreboard = ScoringService.get_scoreboard(team_based=True, limit=100)
        cache_service.set_scoreboard(scoreboard, ttl=60)
    
    return jsonify(scoreboard)


@scoreboard_bp.route('/api/top/<int:limit>')
def get_top_teams(limit):
    """Get top N teams"""
    limit = min(limit, 100)  # Cap at 100
    
    scoreboard = cache_service.get_scoreboard()
    
    if not scoreboard:
        scoreboard = ScoringService.get_scoreboard(team_based=True, limit=limit)
        cache_service.set_scoreboard(scoreboard, ttl=60)
    else:
        scoreboard = scoreboard[:limit]
    
    return jsonify(scoreboard)


@scoreboard_bp.route('/api/stats')
def get_platform_stats():
    """Get overall platform statistics"""
    stats = cache_service.get_stats()
    
    if not stats:
        from models.user import User
        from models.team import Team
        from models.challenge import Challenge
        from models.submission import Submission, Solve
        
        stats = {
            'total_users': User.query.count(),
            'total_teams': Team.query.filter_by(is_active=True).count(),
            'total_challenges': Challenge.query.filter_by(is_visible=True).count(),
            'total_submissions': Submission.query.count(),
            'total_solves': Solve.query.count(),
            'challenges_by_category': {}
        }
        
        # Get challenges by category
        challenges = Challenge.query.filter_by(is_visible=True).all()
        for challenge in challenges:
            cat = challenge.category
            if cat not in stats['challenges_by_category']:
                stats['challenges_by_category'][cat] = 0
            stats['challenges_by_category'][cat] += 1
        
        cache_service.set_stats(stats, ttl=300)
    
    return jsonify(stats)
