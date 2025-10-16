from flask import Blueprint, render_template, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from services.scoring import ScoringService
from services.cache import cache_service

scoreboard_bp = Blueprint('scoreboard', __name__, url_prefix='/scoreboard')

@scoreboard_bp.route('/')
def view_scoreboard():
    """View scoreboard page"""
    from models.settings import Settings
    
    # Check if CTF has started (admins bypass this check)
    is_admin = current_user.is_authenticated and current_user.is_admin
    if not is_admin and not Settings.is_ctf_started():
        start_time = Settings.get('ctf_start_time', type='datetime')
        return render_template('countdown.html', 
                             start_time=start_time,
                             page_title='Scoreboard',
                             return_url=url_for('scoreboard.view_scoreboard'))
    
    # Check if scoreboard is visible to users
    scoreboard_visible = Settings.get('scoreboard_visible', default=True, type='bool')
    
    # If scoreboard is hidden and user is not admin, redirect
    if not scoreboard_visible and (not current_user.is_authenticated or not current_user.is_admin):
        flash('The scoreboard is currently hidden by the admins.', 'info')
        return redirect(url_for('index'))
    
    # Check if teams are enabled
    teams_enabled = Settings.get('teams_enabled', default=True, type='bool')
    
    return render_template('scoreboard.html', teams_enabled=teams_enabled, scoreboard_visible=scoreboard_visible)


@scoreboard_bp.route('/api/data')
def get_scoreboard_data():
    """Get scoreboard data (API endpoint)"""
    from models.settings import Settings
    
    # Check if CTF has started (admins bypass this check)
    is_admin = current_user.is_authenticated and current_user.is_admin
    if not is_admin and not Settings.is_ctf_started():
        return jsonify([])
    
    # Check if scoreboard is visible to users
    scoreboard_visible = Settings.get('scoreboard_visible', default=True, type='bool')
    
    # If scoreboard is hidden and user is not admin, return empty
    if not scoreboard_visible and (not current_user.is_authenticated or not current_user.is_admin):
        return jsonify([])
    
    # Check if teams are enabled
    teams_enabled = Settings.get('teams_enabled', default=True, type='bool')
    
    # Try cache first
    cache_key = 'scoreboard_team' if teams_enabled else 'scoreboard_individual'
    scoreboard = cache_service.get(cache_key)
    
    if not scoreboard:
        # Generate fresh scoreboard
        scoreboard = ScoringService.get_scoreboard(team_based=teams_enabled, limit=100)
        cache_service.set(cache_key, scoreboard, ttl=60)
    
    return jsonify(scoreboard)


@scoreboard_bp.route('/api/top/<int:limit>')
def get_top_teams(limit):
    """Get top N teams or users"""
    from models.settings import Settings
    
    limit = min(limit, 100)  # Cap at 100
    
    # Check if teams are enabled
    teams_enabled = Settings.get('teams_enabled', default=True, type='bool')
    
    cache_key = 'scoreboard_team' if teams_enabled else 'scoreboard_individual'
    scoreboard = cache_service.get(cache_key)
    
    if not scoreboard:
        scoreboard = ScoringService.get_scoreboard(team_based=teams_enabled, limit=limit)
        cache_service.set(cache_key, scoreboard, ttl=60)
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
