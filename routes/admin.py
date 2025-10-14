from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from functools import wraps
from models import db
from models.user import User
from models.team import Team
from models.challenge import Challenge
from models.submission import Submission, Solve
from models.file import ChallengeFile
from models.hint import Hint, HintUnlock
from services.cache import cache_service
from services.file_storage import file_storage
import json

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Admin access required', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    """Admin dashboard"""
    # Get statistics
    stats = {
        'users': User.query.count(),
        'teams': Team.query.count(),
        'challenges': Challenge.query.count(),
        'submissions': Submission.query.count(),
        'solves': Solve.query.count()
    }
    
    # Recent activity
    recent_solves = Solve.query.order_by(Solve.solved_at.desc()).limit(10).all()
    
    return render_template('admin/dashboard.html', stats=stats, recent_solves=recent_solves)


# Challenge Management
@admin_bp.route('/challenges')
@login_required
@admin_required
def manage_challenges():
    """Manage challenges page"""
    challenges = Challenge.query.all()
    return render_template('admin/challenges.html', challenges=challenges)


@admin_bp.route('/challenges/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_challenge():
    """Create a new challenge"""
    if request.method == 'POST':
        data = request.form
        
        challenge = Challenge(
            name=data.get('name'),
            description=data.get('description'),
            category=data.get('category'),
            flag=data.get('flag'),
            flag_case_sensitive=data.get('flag_case_sensitive') == 'true',
            initial_points=int(data.get('initial_points', 500)),
            minimum_points=int(data.get('minimum_points', 50)),
            decay_solves=int(data.get('decay_solves', 30)),
            max_attempts=int(data.get('max_attempts', 0)),
            is_visible=data.get('is_visible') == 'true',
            is_dynamic=data.get('is_dynamic') == 'true',
            requires_team=data.get('requires_team') == 'true',
            author=data.get('author'),
            difficulty=data.get('difficulty')
        )
        
        db.session.add(challenge)
        db.session.flush()  # Get challenge ID
        
        # Handle hints
        hint_contents = request.form.getlist('hint_content[]')
        hint_costs = request.form.getlist('hint_cost[]')
        hint_orders = request.form.getlist('hint_order[]')
        
        for i in range(len(hint_contents)):
            if hint_contents[i].strip():
                hint = Hint(
                    challenge_id=challenge.id,
                    content=hint_contents[i],
                    cost=int(hint_costs[i]) if i < len(hint_costs) else 10,
                    order=int(hint_orders[i]) if i < len(hint_orders) else (i + 1)
                )
                db.session.add(hint)
        
        # Handle file uploads
        uploaded_files = []
        if 'files' in request.files:
            files = request.files.getlist('files')
            for file in files:
                if file and file.filename:
                    try:
                        file_info = file_storage.save_challenge_file(file, challenge.id)
                        if file_info:
                            # Create ChallengeFile record
                            challenge_file = ChallengeFile(
                                challenge_id=challenge.id,
                                original_filename=file_info['original_filename'],
                                stored_filename=file_info['stored_filename'],
                                filepath=file_info['filepath'],
                                relative_path=file_info['relative_path'],
                                file_hash=file_info['hash'],
                                file_size=file_info['size'],
                                uploaded_by=current_user.id
                            )
                            db.session.add(challenge_file)
                            uploaded_files.append(file_info)
                    except Exception as e:
                        flash(f'Error uploading file {file.filename}: {str(e)}', 'warning')
        
        # Store file URLs in challenge (for backward compatibility)
        if uploaded_files:
            file_urls = [f['url'] for f in uploaded_files]
            challenge.files = json.dumps(file_urls)
        
        db.session.commit()
        
        cache_service.invalidate_all_challenges()
        
        flash(f'Challenge "{challenge.name}" created successfully!', 'success')
        return redirect(url_for('admin.manage_challenges'))
    
    return render_template('admin/create_challenge.html')


@admin_bp.route('/challenges/<int:challenge_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_challenge(challenge_id):
    """Edit a challenge"""
    challenge = Challenge.query.get_or_404(challenge_id)
    
    if request.method == 'POST':
        data = request.form
        
        challenge.name = data.get('name')
        challenge.description = data.get('description')
        challenge.category = data.get('category')
        challenge.flag = data.get('flag')
        challenge.flag_case_sensitive = data.get('flag_case_sensitive') == 'true'
        challenge.initial_points = int(data.get('initial_points', 500))
        challenge.minimum_points = int(data.get('minimum_points', 50))
        challenge.decay_solves = int(data.get('decay_solves', 30))
        challenge.max_attempts = int(data.get('max_attempts', 0))
        challenge.is_visible = data.get('is_visible') == 'true'
        challenge.is_dynamic = data.get('is_dynamic') == 'true'
        challenge.requires_team = data.get('requires_team') == 'true'
        challenge.author = data.get('author')
        challenge.difficulty = data.get('difficulty')
        
        # Handle existing hints updates
        existing_hints = Hint.query.filter_by(challenge_id=challenge_id).all()
        for hint in existing_hints:
            content_key = f'existing_hint_content_{hint.id}'
            cost_key = f'existing_hint_cost_{hint.id}'
            order_key = f'existing_hint_order_{hint.id}'
            
            if content_key in data:
                hint.content = data[content_key]
                hint.cost = int(data[cost_key])
                hint.order = int(data[order_key])
        
        # Handle new hints
        hint_contents = request.form.getlist('hint_content[]')
        hint_costs = request.form.getlist('hint_cost[]')
        hint_orders = request.form.getlist('hint_order[]')
        
        for i in range(len(hint_contents)):
            if hint_contents[i].strip():
                hint = Hint(
                    challenge_id=challenge.id,
                    content=hint_contents[i],
                    cost=int(hint_costs[i]) if i < len(hint_costs) else 10,
                    order=int(hint_orders[i]) if i < len(hint_orders) else (i + 1)
                )
                db.session.add(hint)
        
        # Handle new file uploads
        if 'files' in request.files:
            files = request.files.getlist('files')
            uploaded_files = []
            
            for file in files:
                if file and file.filename:
                    try:
                        file_info = file_storage.save_challenge_file(file, challenge.id)
                        if file_info:
                            # Create ChallengeFile record
                            challenge_file = ChallengeFile(
                                challenge_id=challenge.id,
                                original_filename=file_info['original_filename'],
                                stored_filename=file_info['stored_filename'],
                                filepath=file_info['filepath'],
                                relative_path=file_info['relative_path'],
                                file_hash=file_info['hash'],
                                file_size=file_info['size'],
                                uploaded_by=current_user.id
                            )
                            db.session.add(challenge_file)
                            uploaded_files.append(file_info)
                    except Exception as e:
                        flash(f'Error uploading file {file.filename}: {str(e)}', 'warning')
            
            # Update file URLs if new files were uploaded
            if uploaded_files:
                existing_urls = json.loads(challenge.files) if challenge.files else []
                new_urls = [f['url'] for f in uploaded_files]
                all_urls = existing_urls + new_urls
                challenge.files = json.dumps(all_urls)
        
        db.session.commit()
        
        cache_service.invalidate_challenge(challenge_id)
        cache_service.invalidate_all_challenges()
        
        flash(f'Challenge "{challenge.name}" updated successfully!', 'success')
        return redirect(url_for('admin.manage_challenges'))
    
    # Get existing files and hints
    existing_files = ChallengeFile.query.filter_by(challenge_id=challenge_id).all()
    existing_hints = Hint.query.filter_by(challenge_id=challenge_id).order_by(Hint.order).all()
    
    return render_template('admin/edit_challenge.html', 
                          challenge=challenge, 
                          existing_files=existing_files,
                          existing_hints=existing_hints)


@admin_bp.route('/challenges/<int:challenge_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_challenge(challenge_id):
    """Delete a challenge"""
    challenge = Challenge.query.get_or_404(challenge_id)
    
    # Delete associated files
    file_storage.delete_challenge_files(challenge_id)
    
    db.session.delete(challenge)
    db.session.commit()
    
    cache_service.invalidate_challenge(challenge_id)
    cache_service.invalidate_all_challenges()
    cache_service.invalidate_scoreboard()
    
    return jsonify({'success': True, 'message': 'Challenge deleted'})


@admin_bp.route('/challenges/<int:challenge_id>/toggle-enabled', methods=['POST'])
@login_required
@admin_required
def toggle_challenge_enabled(challenge_id):
    """Toggle challenge enabled status"""
    challenge = Challenge.query.get_or_404(challenge_id)
    
    challenge.is_enabled = not challenge.is_enabled
    db.session.commit()
    
    cache_service.invalidate_challenge(challenge_id)
    cache_service.invalidate_all_challenges()
    
    status = "enabled" if challenge.is_enabled else "disabled"
    return jsonify({
        'success': True,
        'is_enabled': challenge.is_enabled,
        'message': f'Challenge {challenge.name} {status}'
    })


@admin_bp.route('/challenges/files/<int:file_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_challenge_file(file_id):
    """Delete a challenge file"""
    challenge_file = ChallengeFile.query.get_or_404(file_id)
    challenge_id = challenge_file.challenge_id
    
    # Delete physical file
    file_storage.delete_file(challenge_file.filepath)
    
    # Delete database record
    db.session.delete(challenge_file)
    db.session.commit()
    
    cache_service.invalidate_challenge(challenge_id)
    
    return jsonify({'success': True, 'message': 'File deleted'})


# User Management
@admin_bp.route('/users')
@login_required
@admin_required
def manage_users():
    """Manage users page"""
    users = User.query.all()
    return render_template('admin/users.html', users=users)


@admin_bp.route('/users/<int:user_id>/toggle-admin', methods=['POST'])
@login_required
@admin_required
def toggle_admin(user_id):
    """Toggle admin status for a user"""
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        return jsonify({'success': False, 'message': 'Cannot modify your own admin status'}), 400
    
    user.is_admin = not user.is_admin
    db.session.commit()
    
    return jsonify({
        'success': True,
        'is_admin': user.is_admin,
        'message': f'User {user.username} admin status updated'
    })


@admin_bp.route('/users/<int:user_id>/toggle-active', methods=['POST'])
@login_required
@admin_required
def toggle_active(user_id):
    """Toggle active status for a user"""
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        return jsonify({'success': False, 'message': 'Cannot deactivate yourself'}), 400
    
    user.is_active = not user.is_active
    db.session.commit()
    
    return jsonify({
        'success': True,
        'is_active': user.is_active,
        'message': f'User {user.username} active status updated'
    })


# Team Management
@admin_bp.route('/teams')
@login_required
@admin_required
def manage_teams():
    """Manage teams page"""
    teams = Team.query.all()
    return render_template('admin/teams.html', teams=teams)


@admin_bp.route('/teams/<int:team_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_team(team_id):
    """Delete a team"""
    team = Team.query.get_or_404(team_id)
    
    # Remove team from all members
    members = User.query.filter_by(team_id=team_id).all()
    for member in members:
        member.team_id = None
        member.is_team_captain = False
    
    db.session.delete(team)
    db.session.commit()
    
    cache_service.invalidate_team(team_id)
    cache_service.invalidate_scoreboard()
    
    return jsonify({'success': True, 'message': 'Team deleted'})


# Points Management
@admin_bp.route('/users/<int:user_id>/adjust-points', methods=['POST'])
@login_required
@admin_required
def adjust_user_points(user_id):
    """Manually adjust user points"""
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    
    points_delta = int(data.get('points', 0))
    reason = data.get('reason', 'Manual adjustment by admin')
    
    # Update user score
    user.score = max(0, user.score + points_delta)
    db.session.commit()
    
    cache_service.invalidate_scoreboard()
    
    return jsonify({
        'success': True,
        'new_score': user.score,
        'message': f'Adjusted {user.username} points by {points_delta:+d}'
    })


@admin_bp.route('/teams/<int:team_id>/adjust-points', methods=['POST'])
@login_required
@admin_required
def adjust_team_points(team_id):
    """Manually adjust team points"""
    team = Team.query.get_or_404(team_id)
    data = request.get_json()
    
    points_delta = int(data.get('points', 0))
    reason = data.get('reason', 'Manual adjustment by admin')
    
    # Update team score
    team.score = max(0, team.score + points_delta)
    db.session.commit()
    
    cache_service.invalidate_scoreboard()
    
    return jsonify({
        'success': True,
        'new_score': team.score,
        'message': f'Adjusted {team.name} points by {points_delta:+d}'
    })


# Settings
@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def settings():
    """Platform settings"""
    from models.settings import Settings
    
    if request.method == 'POST':
        # This would update configuration
        # For now, just show success message
        flash('Settings updated successfully!', 'success')
        return redirect(url_for('admin.settings'))
    
    import flask
    
    # Get CTF control settings
    ctf_settings = {
        'start_time': Settings.get('ctf_start_time'),
        'end_time': Settings.get('ctf_end_time'),
        'is_paused': Settings.get('ctf_paused', False),
        'status': Settings.get_ctf_status()
    }
    
    return render_template('admin/settings.html', 
                         flask_version=flask.__version__,
                         get_flask_version=lambda: flask.__version__,
                         ctf_settings=ctf_settings)


# CTF Control
@admin_bp.route('/ctf-control', methods=['GET', 'POST'])
@login_required
@admin_required
def ctf_control():
    """CTF control panel for scheduling and pausing"""
    from models.settings import Settings
    from datetime import datetime
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'set_times':
            start_time_str = request.form.get('start_time')
            end_time_str = request.form.get('end_time')
            
            if start_time_str:
                try:
                    start_time = datetime.fromisoformat(start_time_str)
                    Settings.set('ctf_start_time', start_time, 'datetime', 'CTF start time')
                    flash('CTF start time set successfully!', 'success')
                except ValueError:
                    flash('Invalid start time format', 'error')
            
            if end_time_str:
                try:
                    end_time = datetime.fromisoformat(end_time_str)
                    Settings.set('ctf_end_time', end_time, 'datetime', 'CTF end time')
                    flash('CTF end time set successfully!', 'success')
                except ValueError:
                    flash('Invalid end time format', 'error')
        
        elif action == 'clear_times':
            Settings.set('ctf_start_time', None, 'datetime')
            Settings.set('ctf_end_time', None, 'datetime')
            flash('CTF schedule cleared - CTF is now always running', 'success')
        
        elif action == 'pause':
            Settings.set('ctf_paused', True, 'bool', 'CTF paused status')
            flash('CTF paused - Submissions disabled', 'warning')
        
        elif action == 'resume':
            Settings.set('ctf_paused', False, 'bool', 'CTF paused status')
            flash('CTF resumed - Submissions enabled', 'success')
        
        return redirect(url_for('admin.ctf_control'))
    
    # Get current settings
    ctf_settings = {
        'start_time': Settings.get('ctf_start_time'),
        'end_time': Settings.get('ctf_end_time'),
        'is_paused': Settings.get('ctf_paused', False),
        'status': Settings.get_ctf_status()
    }
    
    return render_template('admin/ctf_control.html', ctf_settings=ctf_settings)


# Hint Management
@admin_bp.route('/hints/<int:hint_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_hint(hint_id):
    """Delete a hint"""
    hint = Hint.query.get_or_404(hint_id)
    challenge_id = hint.challenge_id
    
    db.session.delete(hint)
    db.session.commit()
    
    cache_service.invalidate_challenge(challenge_id)
    
    return jsonify({
        'success': True,
        'message': 'Hint deleted successfully'
    })
