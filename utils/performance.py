from functools import wraps
from flask import g
from models import db
from sqlalchemy import event
from sqlalchemy.engine import Engine
import time

# Query performance tracking (development only)
def track_queries(f):
    """Decorator to track database queries for a request"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        g.query_count = 0
        g.query_time = 0
        return f(*args, **kwargs)
    return decorated_function


# Add indexes for frequently queried columns
PERFORMANCE_INDEXES = {
    'users': ['username', 'email', 'is_admin', 'team_id'],
    'teams': ['name', 'invite_code'],
    'challenges': ['name', 'category', 'is_visible', 'is_enabled'],
    'submissions': ['user_id', 'team_id', 'challenge_id', 'is_correct', 'submitted_at'],
    'solves': ['user_id', 'team_id', 'challenge_id', 'solved_at'],
    'settings': ['key'], 
    'challenge_files': ['challenge_id'],
    'hints': ['challenge_id'],
    'hint_unlocks': ['user_id', 'team_id', 'hint_id'],
}

# Common query optimizations
EAGER_LOADING = {
    # When loading challenges, also load files and hints
    'challenge_list': {
        'model': 'Challenge',
        'joinedload': ['files', 'hints']
    },
    
    # When loading solves, also load user and team
    'solve_list': {
        'model': 'Solve',
        'joinedload': ['user', 'team', 'challenge']
    },
    
    # When loading submissions, also load user and challenge
    'submission_list': {
        'model': 'Submission',
        'joinedload': ['user', 'challenge']
    },
    
    # When loading users, also load team
    'user_list': {
        'model': 'User',
        'joinedload': ['team']
    },
}


def optimize_query(query, eager_load=None):
    """
    Optimize a query by adding eager loading
    
    Usage:
        from utils.performance import optimize_query
        
        # Load challenges with files
        query = Challenge.query.filter_by(is_visible=True)
        query = optimize_query(query, ['files', 'hints'])
        challenges = query.all()
    """
    from sqlalchemy.orm import joinedload
    
    if eager_load:
        for relation in eager_load:
            query = query.options(joinedload(relation))
    
    return query


def get_cached_setting(key, default=None):
    """
    Get a setting value with Redis caching
    Falls back to Settings.get() if cache miss
    """
    from models.settings import Settings
    from services.cache import cache_service
    
    # Try cache first
    cache_key = f'setting:{key}'
    value = cache_service.get(cache_key)
    
    if value is None:
        # Cache miss, get from database
        value = Settings.get(key, default)
        # Cache for 5 minutes
        cache_service.set(cache_key, value, timeout=300)
    
    return value


def batch_load_challenges(challenge_ids):
    """
    Load multiple challenges in a single query
    More efficient than loading one by one
    """
    from models.challenge import Challenge
    from sqlalchemy.orm import joinedload
    
    challenges = Challenge.query.filter(
        Challenge.id.in_(challenge_ids)
    ).options(
        joinedload(Challenge.files),
        joinedload(Challenge.hints)
    ).all()
    
    return {c.id: c for c in challenges}


def batch_load_users(user_ids):
    """
    Load multiple users in a single query
    """
    from models.user import User
    from sqlalchemy.orm import joinedload
    
    users = User.query.filter(
        User.id.in_(user_ids)
    ).options(
        joinedload(User.team)
    ).all()
    
    return {u.id: u for u in users}


def batch_check_solves(user_id, challenge_ids):
    """
    Check if user has solved multiple challenges in one query
    More efficient than checking one by one
    """
    from models.submission import Solve
    
    solves = Solve.query.filter(
        Solve.user_id == user_id,
        Solve.challenge_id.in_(challenge_ids)
    ).all()
    
    return {s.challenge_id for s in solves}


def get_scoreboard_cached(team_mode=False, limit=None):
    """
    Get scoreboard with caching (5 minute cache)
    """
    from services.cache import cache_service
    from services.scoring import ScoringService
    
    cache_key = f'scoreboard:{"team" if team_mode else "user"}:{limit or "all"}'
    
    # Try cache first
    scoreboard = cache_service.get(cache_key)
    
    if scoreboard is None:
        # Cache miss, calculate
        if team_mode:
            scoreboard = ScoringService.get_team_scoreboard(limit=limit)
        else:
            scoreboard = ScoringService.get_user_scoreboard(limit=limit)
        
        # Cache for 5 minutes
        cache_service.set(cache_key, scoreboard, timeout=300)
    
    return scoreboard


def clear_scoreboard_cache():
    """Clear scoreboard cache after a solve"""
    from services.cache import cache_service
    
    # Clear all scoreboard variants
    cache_service.delete('scoreboard:user:all')
    cache_service.delete('scoreboard:team:all')
    cache_service.delete('scoreboard:user:10')
    cache_service.delete('scoreboard:team:10')
    cache_service.delete('scoreboard:user:50')
    cache_service.delete('scoreboard:team:50')
    cache_service.delete('scoreboard:user:100')
    cache_service.delete('scoreboard:team:100')


