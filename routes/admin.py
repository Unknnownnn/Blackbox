from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime
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
        from models.branching import ChallengeFlag
        
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
        
        # Create primary flag entry in challenge_flags table
        primary_flag = ChallengeFlag(
            challenge_id=challenge.id,
            flag_value=data.get('flag'),
            flag_label='Primary Flag',
            is_case_sensitive=data.get('flag_case_sensitive') == 'true'
        )
        db.session.add(primary_flag)
        
        # Handle additional flags
        additional_flags = request.form.getlist('additional_flags[]')
        flag_labels = request.form.getlist('flag_labels[]')
        flag_points = request.form.getlist('flag_points[]')
        flag_cases = request.form.getlist('flag_case[]')
        
        for i in range(len(additional_flags)):
            if additional_flags[i].strip():
                points_override = None
                if i < len(flag_points) and flag_points[i].strip():
                    try:
                        points_override = int(flag_points[i])
                    except ValueError:
                        pass
                
                additional_flag = ChallengeFlag(
                    challenge_id=challenge.id,
                    flag_value=additional_flags[i].strip(),
                    flag_label=flag_labels[i].strip() if i < len(flag_labels) and flag_labels[i].strip() else None,
                    points_override=points_override,
                    is_case_sensitive=flag_cases[i] == 'true' if i < len(flag_cases) else True
                )
                db.session.add(additional_flag)
        
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
    
    # Delete associated branching data first
    from models.branching import ChallengeFlag, ChallengePrerequisite, ChallengeUnlock
    
    # Delete all flags for this challenge
    ChallengeFlag.query.filter_by(challenge_id=challenge_id).delete()
    
    # Delete all flags that unlock this challenge
    ChallengeFlag.query.filter_by(unlocks_challenge_id=challenge_id).update(
        {'unlocks_challenge_id': None}
    )
    
    # Delete prerequisites where this challenge is required or is the dependent
    ChallengePrerequisite.query.filter(
        db.or_(
            ChallengePrerequisite.challenge_id == challenge_id,
            ChallengePrerequisite.prerequisite_challenge_id == challenge_id
        )
    ).delete()
    
    # Delete unlock records
    ChallengeUnlock.query.filter_by(challenge_id=challenge_id).delete()
    
    # Delete associated files
    file_storage.delete_challenge_files(challenge_id)
    
    # Now delete the challenge itself
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
    """Manually adjust user points by creating a solve adjustment"""
    from models.submission import Solve
    from models.challenge import Challenge
    
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    
    points_delta = int(data.get('points', 0))
    reason = data.get('reason', 'Manual adjustment by admin')
    
    if points_delta == 0:
        return jsonify({'success': False, 'message': 'Points delta cannot be zero'}), 400
    
    # Create a "virtual" solve record for tracking score adjustments
    # We'll create a challenge with ID 0 that represents manual adjustments
    adjustment = Solve(
        user_id=user_id,
        team_id=user.team_id,
        challenge_id=None,  # None indicates manual adjustment
        points_earned=points_delta,
        solved_at=datetime.utcnow()
    )
    
    db.session.add(adjustment)
    db.session.commit()
    
    cache_service.invalidate_scoreboard()
    if user.team_id:
        cache_service.invalidate_team(user.team_id)
    cache_service.invalidate_user(user_id)
    
    return jsonify({
        'success': True,
        'new_score': user.get_score(),
        'message': f'Adjusted {user.username} points by {points_delta:+d}. Reason: {reason}'
    })


@admin_bp.route('/teams/<int:team_id>/adjust-points', methods=['POST'])
@login_required
@admin_required
def adjust_team_points(team_id):
    """Manually adjust team points by creating a solve adjustment"""
    from models.submission import Solve
    
    team = Team.query.get_or_404(team_id)
    data = request.get_json()
    
    points_delta = int(data.get('points', 0))
    reason = data.get('reason', 'Manual adjustment by admin')
    
    if points_delta == 0:
        return jsonify({'success': False, 'message': 'Points delta cannot be zero'}), 400
    
    # Create adjustment solve for team
    adjustment = Solve(
        user_id=None,
        team_id=team_id,
        challenge_id=None,
        points_earned=points_delta,
        solved_at=datetime.utcnow()
    )
    
    db.session.add(adjustment)
    db.session.commit()
    
    cache_service.invalidate_scoreboard()
    cache_service.invalidate_team(team_id)
    
    return jsonify({
        'success': True,
        'new_score': team.get_score(),
        'message': f'Adjusted {team.name} points by {points_delta:+d}. Reason: {reason}'
    })


@admin_bp.route('/users/<int:user_id>/solves', methods=['GET'])
@login_required
@admin_required
def get_user_solves(user_id):
    """Get solve history for a user including manual adjustments"""
    from models.submission import Solve
    from models.challenge import Challenge
    
    user = User.query.get_or_404(user_id)
    
    solves = db.session.query(Solve, Challenge).outerjoin(
        Challenge, Solve.challenge_id == Challenge.id
    ).filter(
        Solve.user_id == user_id
    ).order_by(Solve.solved_at.desc()).all()
    
    solve_list = []
    for solve, challenge in solves:
        solve_list.append({
            'challenge_name': challenge.name if challenge else None,
            'points': solve.points_earned,
            'solved_at': solve.solved_at.isoformat(),
            'is_adjustment': challenge is None,
            'reason': None  # Could add reason field to Solve model
        })
    
    return jsonify({
        'success': True,
        'solves': solve_list
    })


@admin_bp.route('/teams/<int:team_id>/solves', methods=['GET'])
@login_required
@admin_required
def get_team_solves(team_id):
    """Get solve history for a team including manual adjustments"""
    from models.submission import Solve
    from models.challenge import Challenge
    
    team = Team.query.get_or_404(team_id)
    
    solves = db.session.query(Solve, Challenge).outerjoin(
        Challenge, Solve.challenge_id == Challenge.id
    ).filter(
        Solve.team_id == team_id
    ).order_by(Solve.solved_at.desc()).all()
    
    solve_list = []
    for solve, challenge in solves:
        solve_list.append({
            'challenge_name': challenge.name if challenge else None,
            'points': solve.points_earned,
            'solved_at': solve.solved_at.isoformat(),
            'is_adjustment': challenge is None,
            'reason': None
        })
    
    return jsonify({
        'success': True,
        'solves': solve_list
    })

    data = request.get_json()
    
    points_delta = int(data.get('points', 0))
    reason = data.get('reason', 'Manual adjustment by admin')
    
    if points_delta == 0:
        return jsonify({'success': False, 'message': 'Points delta cannot be zero'}), 400
    
    # Create a "virtual" solve record for the team
    # Use the first team member as the user, or None if no members
    first_member = team.members.first()
    
    adjustment = Solve(
        user_id=first_member.id if first_member else None,
        team_id=team_id,
        challenge_id=None,  # None indicates manual adjustment
        points_earned=points_delta,
        solved_at=datetime.utcnow()
    )
    
    db.session.add(adjustment)
    db.session.commit()
    
    cache_service.invalidate_scoreboard()
    cache_service.invalidate_team(team_id)
    
    return jsonify({
        'success': True,
        'new_score': team.get_score(),
        'message': f'Adjusted {team.name} points by {points_delta:+d}. Reason: {reason}'
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
    
    # Get all settings
    all_settings = Settings.get_all()
    
    return render_template('admin/settings.html', 
                         flask_version=flask.__version__,
                         get_flask_version=lambda: flask.__version__,
                         ctf_settings=ctf_settings,
                         settings=all_settings)


@admin_bp.route('/settings/event-config', methods=['POST'])
@login_required
@admin_required
def update_event_config():
    """Update event configuration (name, logo, description)"""
    from models.settings import Settings
    import os
    from werkzeug.utils import secure_filename
    
    try:
        # Update CTF name
        ctf_name = request.form.get('ctf_name', '').strip()
        if ctf_name:
            Settings.set('ctf_name', ctf_name, 'string', 'Name of the CTF event')
        
        # Update CTF description
        ctf_description = request.form.get('ctf_description', '').strip()
        if ctf_description:
            Settings.set('ctf_description', ctf_description, 'string', 'Description of the CTF event')
        
        # Update registration and team mode settings
        allow_registration = 'allow_registration' in request.form
        Settings.set('allow_registration', allow_registration, 'bool', 'Allow new user registrations')
        
        teams_enabled = 'teams_enabled' in request.form
        Settings.set('teams_enabled', teams_enabled, 'bool', 'Enable teams feature (for solo competitions)')
        
        team_mode = 'team_mode' in request.form
        Settings.set('team_mode', team_mode, 'bool', 'Enable team-based CTF mode')
        
        # Update scoreboard visibility
        scoreboard_visible = 'scoreboard_visible' in request.form
        Settings.set('scoreboard_visible', scoreboard_visible, 'bool', 'Show scoreboard to users')
        
        # Update first blood bonus
        first_blood_bonus = request.form.get('first_blood_bonus', '0')
        try:
            first_blood_bonus = int(first_blood_bonus)
            Settings.set('first_blood_bonus', first_blood_bonus, 'int', 'Bonus points for first blood')
        except ValueError:
            pass  # Ignore invalid values
        
        # Handle logo upload
        if 'ctf_logo' in request.files:
            logo_file = request.files['ctf_logo']
            if logo_file and logo_file.filename:
                from flask import current_app
                
                # Use /var/uploads/logos (volume-mounted writable directory)
                uploads_dir = '/var/uploads/logos'
                
                # Create uploads directory if it doesn't exist
                os.makedirs(uploads_dir, exist_ok=True)
                
                # Secure the filename
                filename = secure_filename(logo_file.filename)
                
                # Add timestamp to avoid conflicts
                from datetime import datetime
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                name, ext = os.path.splitext(filename)
                filename = f'ctf_logo_{timestamp}{ext}'
                
                # Save the file
                filepath = os.path.join(uploads_dir, filename)
                logo_file.save(filepath)
                
                # Store relative path in settings
                Settings.set('ctf_logo', filename, 'string', 'Path to CTF logo image')
        
        flash('Event configuration updated successfully!', 'success')
    except Exception as e:
        flash(f'Error updating configuration: {str(e)}', 'error')
    
    return redirect(url_for('admin.settings'))


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


# Challenge Branching Management
@admin_bp.route('/branching')
@login_required
@admin_required
def manage_branching():
    """Manage challenge branching and prerequisites"""
    challenges = Challenge.query.order_by(Challenge.name).all()
    return render_template('admin/branching.html', challenges=challenges)


@admin_bp.route('/branching/flags', methods=['GET'])
@login_required
@admin_required
def get_flags():
    """Get all challenge flags"""
    from models.branching import ChallengeFlag
    
    flags = ChallengeFlag.query.all()
    flags_data = []
    
    for flag in flags:
        flag_dict = flag.to_dict(include_value=True)
        flag_dict['challenge_name'] = flag.challenge.name if flag.challenge else None
        flag_dict['unlocks_challenge_name'] = flag.unlocks_challenge.name if flag.unlocks_challenge else None
        flags_data.append(flag_dict)
    
    return jsonify({'success': True, 'flags': flags_data})


@admin_bp.route('/branching/flags', methods=['POST'])
@login_required
@admin_required
def add_flag():
    """Add a new flag to a challenge"""
    from models.branching import ChallengeFlag
    
    challenge_id = request.form.get('challenge_id')
    flag_value = request.form.get('flag_value', '').strip()
    flag_label = request.form.get('flag_label', '').strip()
    unlocks_challenge_id = request.form.get('unlocks_challenge_id')
    points_override = request.form.get('points_override')
    is_case_sensitive = request.form.get('is_case_sensitive', '1') == '1'
    
    if not challenge_id or not flag_value:
        return jsonify({'success': False, 'message': 'Challenge and flag value are required'}), 400
    
    # Validate challenge exists
    challenge = Challenge.query.get(challenge_id)
    if not challenge:
        return jsonify({'success': False, 'message': 'Challenge not found'}), 404
    
    # Validate unlocks_challenge exists if provided
    if unlocks_challenge_id:
        unlocks_challenge = Challenge.query.get(unlocks_challenge_id)
        if not unlocks_challenge:
            return jsonify({'success': False, 'message': 'Unlocks challenge not found'}), 404
    else:
        unlocks_challenge_id = None
    
    # Convert points_override
    if points_override and points_override.strip():
        try:
            points_override = int(points_override)
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid points override'}), 400
    else:
        points_override = None
    
    # Create flag
    new_flag = ChallengeFlag(
        challenge_id=challenge_id,
        flag_value=flag_value,
        flag_label=flag_label if flag_label else None,
        unlocks_challenge_id=unlocks_challenge_id,
        points_override=points_override,
        is_case_sensitive=is_case_sensitive
    )
    
    db.session.add(new_flag)
    db.session.commit()
    
    cache_service.invalidate_challenge(challenge_id)
    
    return jsonify({'success': True, 'message': 'Flag added successfully', 'flag': new_flag.to_dict()})


@admin_bp.route('/branching/flags/<int:flag_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_flag(flag_id):
    """Delete a challenge flag"""
    from models.branching import ChallengeFlag
    
    flag = ChallengeFlag.query.get_or_404(flag_id)
    challenge_id = flag.challenge_id
    
    db.session.delete(flag)
    db.session.commit()
    
    cache_service.invalidate_challenge(challenge_id)
    
    return jsonify({'success': True, 'message': 'Flag deleted successfully'})


@admin_bp.route('/branching/prerequisites', methods=['GET'])
@login_required
@admin_required
def get_prerequisites():
    """Get all challenge prerequisites"""
    from models.branching import ChallengePrerequisite
    
    prerequisites = ChallengePrerequisite.query.all()
    prereqs_data = []
    
    for prereq in prerequisites:
        prereq_dict = prereq.to_dict()
        prereq_dict['challenge_name'] = prereq.challenge.name if prereq.challenge else None
        prereq_dict['prerequisite_name'] = prereq.prerequisite_challenge.name if prereq.prerequisite_challenge else None
        prereqs_data.append(prereq_dict)
    
    return jsonify({'success': True, 'prerequisites': prereqs_data})


@admin_bp.route('/branching/prerequisites', methods=['POST'])
@login_required
@admin_required
def add_prerequisite():
    """Add a prerequisite to a challenge"""
    from models.branching import ChallengePrerequisite
    
    challenge_id = request.form.get('challenge_id')
    prerequisite_challenge_id = request.form.get('prerequisite_challenge_id')
    
    if not challenge_id or not prerequisite_challenge_id:
        return jsonify({'success': False, 'message': 'Both challenge and prerequisite are required'}), 400
    
    # Check if same challenge
    if challenge_id == prerequisite_challenge_id:
        return jsonify({'success': False, 'message': 'A challenge cannot be a prerequisite of itself'}), 400
    
    # Validate both challenges exist
    challenge = Challenge.query.get(challenge_id)
    prereq_challenge = Challenge.query.get(prerequisite_challenge_id)
    
    if not challenge or not prereq_challenge:
        return jsonify({'success': False, 'message': 'Challenge(s) not found'}), 404
    
    # Check if prerequisite already exists
    existing = ChallengePrerequisite.query.filter_by(
        challenge_id=challenge_id,
        prerequisite_challenge_id=prerequisite_challenge_id
    ).first()
    
    if existing:
        return jsonify({'success': False, 'message': 'This prerequisite already exists'}), 400
    
    # TODO: Check for circular dependencies
    
    # Create prerequisite
    new_prereq = ChallengePrerequisite(
        challenge_id=challenge_id,
        prerequisite_challenge_id=prerequisite_challenge_id
    )
    
    db.session.add(new_prereq)
    
    # Automatically set unlock_mode to 'prerequisite' and hide the challenge
    if challenge.unlock_mode != 'prerequisite':
        challenge.unlock_mode = 'prerequisite'
        challenge.is_hidden = True
    
    db.session.commit()
    
    cache_service.invalidate_challenge(challenge_id)
    
    return jsonify({
        'success': True, 
        'message': 'Prerequisite added successfully. Challenge is now hidden until prerequisite is solved.',
        'prerequisite': new_prereq.to_dict()
    })


@admin_bp.route('/branching/prerequisites/<int:prereq_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_prerequisite(prereq_id):
    """Delete a challenge prerequisite"""
    from models.branching import ChallengePrerequisite
    
    prereq = ChallengePrerequisite.query.get_or_404(prereq_id)
    challenge_id = prereq.challenge_id
    
    db.session.delete(prereq)
    db.session.commit()
    
    cache_service.invalidate_challenge(challenge_id)
    
    return jsonify({'success': True, 'message': 'Prerequisite deleted successfully'})


@admin_bp.route('/branching/unlock-mode/<int:challenge_id>', methods=['PUT'])
@login_required
@admin_required
def update_unlock_mode(challenge_id):
    """Update challenge unlock mode and hidden status"""
    challenge = Challenge.query.get_or_404(challenge_id)
    
    data = request.get_json()
    unlock_mode = data.get('unlock_mode')
    is_hidden = data.get('is_hidden', False)
    
    if unlock_mode not in ['none', 'prerequisite', 'flag_unlock']:
        return jsonify({'success': False, 'message': 'Invalid unlock mode'}), 400
    
    challenge.unlock_mode = unlock_mode
    challenge.is_hidden = is_hidden
    
    db.session.commit()
    
    cache_service.invalidate_challenge(challenge_id)
    
    return jsonify({'success': True, 'message': 'Unlock mode updated successfully'})


@admin_bp.route('/branching/challenges/<int:challenge_id>/flags', methods=['GET'])
@login_required
@admin_required
def get_challenge_flags(challenge_id):
    """Get all flags for a specific challenge"""
    from models.branching import ChallengeFlag
    
    flags = ChallengeFlag.query.filter_by(challenge_id=challenge_id).all()
    flags_data = [flag.to_dict(include_value=True) for flag in flags]
    
    return jsonify({'success': True, 'flags': flags_data})


@admin_bp.route('/branching/flags/<int:flag_id>/unlock', methods=['PUT'])
@login_required
@admin_required
def update_flag_unlock(flag_id):
    """Update which challenge a flag unlocks"""
    from models.branching import ChallengeFlag
    
    flag = ChallengeFlag.query.get_or_404(flag_id)
    data = request.get_json()
    unlocks_challenge_id = data.get('unlocks_challenge_id')
    
    # Validate unlocks_challenge exists if provided
    if unlocks_challenge_id:
        unlocks_challenge = Challenge.query.get(unlocks_challenge_id)
        if not unlocks_challenge:
            return jsonify({'success': False, 'message': 'Target challenge not found'}), 404
        
        # Auto-configure the target challenge for flag unlocking
        if unlocks_challenge.unlock_mode != 'flag_unlock':
            unlocks_challenge.unlock_mode = 'flag_unlock'
            unlocks_challenge.is_hidden = True
    
    flag.unlocks_challenge_id = unlocks_challenge_id
    db.session.commit()
    
    cache_service.invalidate_challenge(flag.challenge_id)
    if unlocks_challenge_id:
        cache_service.invalidate_challenge(unlocks_challenge_id)
    
    message = 'Branching configured successfully'
    if unlocks_challenge_id:
        message += '. Target challenge is now hidden until this flag is submitted.'
    
    return jsonify({'success': True, 'message': message})


@admin_bp.route('/branching/connections', methods=['GET'])
@login_required
@admin_required
def get_branching_connections():
    """Get all branching connections (flags that unlock challenges)"""
    from models.branching import ChallengeFlag
    
    flags = ChallengeFlag.query.filter(ChallengeFlag.unlocks_challenge_id.isnot(None)).all()
    connections = []
    
    for flag in flags:
        connections.append({
            'flag_id': flag.id,
            'parent_challenge': flag.challenge.name if flag.challenge else 'Unknown',
            'parent_challenge_id': flag.challenge_id,
            'flag_value': flag.flag_value,
            'flag_label': flag.flag_label,
            'child_challenge': flag.unlocks_challenge.name if flag.unlocks_challenge else 'Unknown',
            'child_challenge_id': flag.unlocks_challenge_id
        })
    
    return jsonify({'success': True, 'connections': connections})


@admin_bp.route('/hint-logs')
@login_required
@admin_required
def hint_logs():
    """View hint unlock logs"""
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    # Get all hint unlocks with pagination
    hint_unlocks = HintUnlock.query.order_by(HintUnlock.unlocked_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('admin/hint_logs.html', hint_unlocks=hint_unlocks)


@admin_bp.route('/hint-logs/api')
@login_required
@admin_required
def hint_logs_api():
    """Get hint unlock logs as JSON"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    user_id = request.args.get('user_id', type=int)
    team_id = request.args.get('team_id', type=int)
    challenge_id = request.args.get('challenge_id', type=int)
    
    query = HintUnlock.query
    
    # Apply filters
    if user_id:
        query = query.filter_by(user_id=user_id)
    if team_id:
        query = query.filter_by(team_id=team_id)
    if challenge_id:
        query = query.join(Hint).filter(Hint.challenge_id == challenge_id)
    
    hint_unlocks = query.order_by(HintUnlock.unlocked_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    logs = []
    for unlock in hint_unlocks.items:
        hint = unlock.hint
        challenge = hint.challenge if hint else None
        user = unlock.user
        team = unlock.team
        
        logs.append({
            'id': unlock.id,
            'user': user.username if user else 'Unknown',
            'user_id': unlock.user_id,
            'team': team.name if team else None,
            'team_id': unlock.team_id,
            'challenge': challenge.name if challenge else 'Unknown',
            'challenge_id': challenge.id if challenge else None,
            'hint_order': hint.order if hint else 0,
            'cost': unlock.cost_paid,
            'unlocked_at': unlock.unlocked_at.isoformat()
        })
    
    return jsonify({
        'success': True,
        'logs': logs,
        'total': hint_unlocks.total,
        'pages': hint_unlocks.pages,
        'current_page': hint_unlocks.page
    })
