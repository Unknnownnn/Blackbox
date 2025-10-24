from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app
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
from models.notification import Notification
from services.websocket import WebSocketService

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
        'solves': Solve.query.filter(Solve.challenge_id.isnot(None)).count()
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
            connection_info=data.get('connection_info'),
            initial_points=int(data.get('initial_points', 500)),
            minimum_points=int(data.get('minimum_points', 50)),
            decay_solves=int(data.get('decay_solves', 30)),
            max_attempts=int(data.get('max_attempts', 0)),
            is_visible=data.get('is_visible') == 'true',
            is_dynamic=data.get('is_dynamic') == 'true',
            requires_team=data.get('requires_team') == 'true',
            author=data.get('author'),
            difficulty=data.get('difficulty'),
            # Docker fields
            docker_enabled=data.get('docker_enabled') == 'true',
            docker_image=data.get('docker_image') if data.get('docker_enabled') == 'true' else None,
            docker_connection_info=data.get('docker_connection_info') if data.get('docker_enabled') == 'true' else None,
            docker_flag_path=data.get('docker_flag_path') if data.get('docker_enabled') == 'true' else None,
            detect_regex_sharing=data.get('detect_regex_sharing') == 'true'
        )
        
        db.session.add(challenge)
        db.session.flush()  # Get challenge ID
        
        # Create primary flag entry in challenge_flags table
        primary_flag = ChallengeFlag(
            challenge_id=challenge.id,
            flag_value=data.get('flag'),
            flag_label='Primary Flag',
            is_case_sensitive=data.get('flag_case_sensitive') == 'true',
            is_regex=data.get('is_regex') == 'true'
        )
        db.session.add(primary_flag)
        
        # Handle additional flags
        additional_flags = request.form.getlist('additional_flags[]')
        flag_labels = request.form.getlist('flag_labels[]')
        flag_points = request.form.getlist('flag_points[]')
        flag_cases = request.form.getlist('flag_case[]')
        flag_is_regex = request.form.getlist('flag_is_regex[]')
        
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
                    is_case_sensitive=flag_cases[i] == 'true' if i < len(flag_cases) else True,
                    is_regex=(i < len(flag_is_regex) and flag_is_regex[i] == 'true')
                )
                db.session.add(additional_flag)
        
        # Handle hints
        hint_contents = request.form.getlist('hint_content[]')
        hint_costs = request.form.getlist('hint_cost[]')
        hint_orders = request.form.getlist('hint_order[]')
        hint_requires = request.form.getlist('hint_requires[]')
        
        # First pass: Create hints without prerequisites
        created_hints = {}
        for i in range(len(hint_contents)):
            if hint_contents[i].strip():
                order = int(hint_orders[i]) if i < len(hint_orders) else (i + 1)
                hint = Hint(
                    challenge_id=challenge.id,
                    content=hint_contents[i],
                    cost=int(hint_costs[i]) if i < len(hint_costs) else 10,
                    order=order
                )
                db.session.add(hint)
                created_hints[order] = hint
        
        # Flush to get hint IDs
        db.session.flush()
        
        # Second pass: Set prerequisites based on order
        for i in range(len(hint_contents)):
            if hint_contents[i].strip():
                order = int(hint_orders[i]) if i < len(hint_orders) else (i + 1)
                requires_order = hint_requires[i] if i < len(hint_requires) and hint_requires[i] else None
                
                if requires_order and requires_order.strip():
                    requires_order = int(requires_order)
                    if requires_order in created_hints:
                        created_hints[order].requires_hint_id = created_hints[requires_order].id
        
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
        
        # Handle image uploads
        uploaded_images = []
        if 'images' in request.files:
            images = request.files.getlist('images')
            for image in images:
                if image and image.filename:
                    try:
                        image_info = file_storage.save_challenge_file(image, challenge.id)
                        if image_info:
                            # Create ChallengeFile record for image
                            challenge_image = ChallengeFile(
                                challenge_id=challenge.id,
                                original_filename=image_info['original_filename'],
                                stored_filename=image_info['stored_filename'],
                                filepath=image_info['filepath'],
                                relative_path=image_info['relative_path'],
                                file_hash=image_info['hash'],
                                file_size=image_info['size'],
                                uploaded_by=current_user.id,
                                is_image=True  # Mark as image
                            )
                            db.session.add(challenge_image)
                            uploaded_images.append(image_info)
                    except Exception as e:
                        flash(f'Error uploading image {image.filename}: {str(e)}', 'warning')
        
        # Store image URLs in challenge
        if uploaded_images:
            image_urls = [{'url': img['url'], 'original_filename': img['original_filename']} for img in uploaded_images]
            challenge.images = json.dumps(image_urls)
        
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
        from models.branching import ChallengeFlag
        data = request.form
        
        challenge.name = data.get('name')
        challenge.description = data.get('description')
        challenge.category = data.get('category')
        challenge.flag = data.get('flag')
        challenge.flag_case_sensitive = data.get('flag_case_sensitive') == 'true'
        challenge.connection_info = data.get('connection_info')
        challenge.initial_points = int(data.get('initial_points', 500))
        challenge.minimum_points = int(data.get('minimum_points', 50))
        challenge.decay_solves = int(data.get('decay_solves', 30))
        challenge.max_attempts = int(data.get('max_attempts', 0))
        challenge.is_visible = data.get('is_visible') == 'true'
        challenge.is_dynamic = data.get('is_dynamic') == 'true'
        challenge.requires_team = data.get('requires_team') == 'true'
        challenge.author = data.get('author')
        challenge.difficulty = data.get('difficulty')
        
        # Handle Docker container settings
        challenge.docker_enabled = data.get('docker_enabled') == 'true'
        if challenge.docker_enabled:
            docker_image_value = data.get('docker_image')
            if docker_image_value == 'custom' or not docker_image_value:
                # Use manual input
                challenge.docker_image = data.get('docker_image_manual')
            else:
                # Use selected image
                challenge.docker_image = docker_image_value
            challenge.docker_connection_info = data.get('docker_connection_info', 'http://{host}:{port}')
            # Optional: path inside the container to write the dynamic flag (e.g. /flag.txt)
            challenge.docker_flag_path = data.get('docker_flag_path')
        else:
            challenge.docker_image = None
            challenge.docker_connection_info = None

        # Regex sharing detection toggle
        challenge.detect_regex_sharing = data.get('detect_regex_sharing') == 'true'
        
        # Update primary flag in challenge_flags table
        primary_flag = ChallengeFlag.query.filter_by(
            challenge_id=challenge_id,
            flag_label='Primary Flag'
        ).first()
        
        if primary_flag:
            primary_flag.flag_value = data.get('flag')
            primary_flag.is_case_sensitive = data.get('flag_case_sensitive') == 'true'
            primary_flag.is_regex = data.get('is_regex') == 'true'
        else:
            # Create primary flag if it doesn't exist
            primary_flag = ChallengeFlag(
                challenge_id=challenge_id,
                flag_value=data.get('flag'),
                flag_label='Primary Flag',
                is_case_sensitive=data.get('flag_case_sensitive') == 'true',
                is_regex=data.get('is_regex') == 'true'
            )
            db.session.add(primary_flag)
        
        # Handle existing hints updates
        existing_hints = Hint.query.filter_by(challenge_id=challenge_id).all()
        for hint in existing_hints:
            content_key = f'existing_hint_content_{hint.id}'
            cost_key = f'existing_hint_cost_{hint.id}'
            order_key = f'existing_hint_order_{hint.id}'
            requires_key = f'existing_hint_requires_{hint.id}'
            
            if content_key in data:
                hint.content = data[content_key]
                hint.cost = int(data[cost_key])
                hint.order = int(data[order_key])
                
                # Handle prerequisite
                requires_id = data.get(requires_key)
                if requires_id and requires_id.strip():
                    hint.requires_hint_id = int(requires_id)
                else:
                    hint.requires_hint_id = None
        
        # Handle new hints
        hint_contents = request.form.getlist('hint_content[]')
        hint_costs = request.form.getlist('hint_cost[]')
        hint_orders = request.form.getlist('hint_order[]')
        hint_requires = request.form.getlist('hint_requires[]')
        
        # First pass: Create hints without prerequisites
        created_hints = []
        for i in range(len(hint_contents)):
            if hint_contents[i].strip():
                hint = Hint(
                    challenge_id=challenge.id,
                    content=hint_contents[i],
                    cost=int(hint_costs[i]) if i < len(hint_costs) else 10,
                    order=int(hint_orders[i]) if i < len(hint_orders) else (i + 1)
                )
                db.session.add(hint)
                created_hints.append((hint, i))
        
        # Flush to get IDs for new hints
        db.session.flush()
        
        # Second pass: Set prerequisites for new hints
        for hint, i in created_hints:
            requires_id = hint_requires[i] if i < len(hint_requires) and hint_requires[i] else None
            if requires_id and requires_id.strip():
                hint.requires_hint_id = int(requires_id)
        
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
        
        # Handle new image uploads
        if 'images' in request.files:
            images = request.files.getlist('images')
            uploaded_images = []
            
            for image in images:
                if image and image.filename:
                    try:
                        image_info = file_storage.save_challenge_file(image, challenge.id)
                        if image_info:
                            # Create ChallengeFile record for image
                            challenge_image = ChallengeFile(
                                challenge_id=challenge.id,
                                original_filename=image_info['original_filename'],
                                stored_filename=image_info['stored_filename'],
                                filepath=image_info['filepath'],
                                relative_path=image_info['relative_path'],
                                file_hash=image_info['hash'],
                                file_size=image_info['size'],
                                uploaded_by=current_user.id,
                                is_image=True
                            )
                            db.session.add(challenge_image)
                            uploaded_images.append(image_info)
                    except Exception as e:
                        flash(f'Error uploading image {image.filename}: {str(e)}', 'warning')
            
            # Update image URLs if new images were uploaded
            if uploaded_images:
                existing_imgs = json.loads(challenge.images) if challenge.images else []
                new_imgs = [{'url': img['url'], 'original_filename': img['original_filename']} for img in uploaded_images]
                all_imgs = existing_imgs + new_imgs
                challenge.images = json.dumps(all_imgs)
        
        db.session.commit()
        
        cache_service.invalidate_challenge(challenge_id)
        cache_service.invalidate_all_challenges()
        
        flash(f'Challenge "{challenge.name}" updated successfully!', 'success')
        return redirect(url_for('admin.manage_challenges'))
    
    # Get existing files and hints
    existing_files = ChallengeFile.query.filter_by(challenge_id=challenge_id, is_image=False).all()
    existing_images = ChallengeFile.query.filter_by(challenge_id=challenge_id, is_image=True).all()
    existing_hints = Hint.query.filter_by(challenge_id=challenge_id).order_by(Hint.order).all()
    
    # Get primary flag to check is_regex status
    from models.branching import ChallengeFlag
    primary_flag = ChallengeFlag.query.filter_by(
        challenge_id=challenge_id,
        flag_label='Primary Flag'
    ).first()
    
    return render_template('admin/edit_challenge.html', 
                          challenge=challenge, 
                          existing_files=existing_files,
                          existing_images=existing_images,
                          existing_hints=existing_hints,
                          primary_flag=primary_flag)


@admin_bp.route('/challenges/<int:challenge_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_challenge(challenge_id):
    """Delete a challenge"""
    challenge = Challenge.query.get_or_404(challenge_id)
    
    # Delete associated data in correct order (respecting foreign key constraints)
    from models.branching import ChallengeFlag, ChallengePrerequisite, ChallengeUnlock
    from models.hint import HintUnlock
    
    # Step 1: Delete solves (references challenge_flags.id)
    Solve.query.filter_by(challenge_id=challenge_id).delete()
    
    # Step 2: Delete submissions
    Submission.query.filter_by(challenge_id=challenge_id).delete()
    
    # Step 3: Delete hint unlocks (references hints.id)
    Hint.query.filter_by(challenge_id=challenge_id).delete()
    
    # Step 4: Delete unlock records
    ChallengeUnlock.query.filter_by(challenge_id=challenge_id).delete()
    
    # Step 5: Delete prerequisites where this challenge is required or is the dependent
    ChallengePrerequisite.query.filter(
        db.or_(
            ChallengePrerequisite.challenge_id == challenge_id,
            ChallengePrerequisite.prerequisite_challenge_id == challenge_id
        )
    ).delete()
    
    # Step 6: Delete flags that unlock this challenge (set to NULL)
    ChallengeFlag.query.filter_by(unlocks_challenge_id=challenge_id).update(
        {'unlocks_challenge_id': None}
    )
    
    # Step 7: Delete all flags for this challenge
    ChallengeFlag.query.filter_by(challenge_id=challenge_id).delete()

    # Step 7a: Delete container instances and related events for this challenge
    try:
        from models.container import ContainerInstance, ContainerEvent
        from services.container_manager import container_orchestrator
        import docker

        # Stop and remove any real docker containers, then remove DB records
        instances = ContainerInstance.query.filter_by(challenge_id=challenge_id).all()
        for inst in instances:
            try:
                if container_orchestrator and container_orchestrator.docker_client:
                    try:
                        docker_container = container_orchestrator.docker_client.containers.get(inst.container_id)
                        docker_container.stop(timeout=10)
                        docker_container.remove()
                    except docker.errors.NotFound:
                        pass
                    except Exception as e:
                        current_app.logger.warning(f"Failed to stop/remove container {inst.container_id}: {e}")
            except Exception:
                # If the orchestrator itself isn't available, continue to delete DB records
                pass

            # Delete any container events referencing this instance
            ContainerEvent.query.filter_by(container_instance_id=inst.id).delete()
            # Delete the instance record
            db.session.delete(inst)

        # Also remove any container events that reference the challenge directly
        ContainerEvent.query.filter_by(challenge_id=challenge_id).delete()
    except Exception as e:
        current_app.logger.warning(f"Error cleaning up container records for challenge {challenge_id}: {e}")

    # Step 7b: Remove any flag abuse records referencing this challenge
    try:
        from models.flag_abuse import FlagAbuseAttempt
        FlagAbuseAttempt.query.filter_by(challenge_id=challenge_id).delete()
    except Exception:
        pass
    
    # Step 8: Delete associated files from filesystem
    file_storage.delete_challenge_files(challenge_id)
    
    # Step 9: Delete file records from database
    ChallengeFile.query.filter_by(challenge_id=challenge_id).delete()
    
    # Step 10: Finally delete the challenge itself
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


@admin_bp.route('/challenges/images/<int:image_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_challenge_image(image_id):
    """Delete a challenge image"""
    challenge_image = ChallengeFile.query.get_or_404(image_id)
    challenge_id = challenge_image.challenge_id
    
    # Delete physical file
    file_storage.delete_file(challenge_image.filepath)
    
    # Delete database record
    db.session.delete(challenge_image)
    db.session.commit()
    
    cache_service.invalidate_challenge(challenge_id)
    
    return jsonify({'success': True, 'message': 'Image deleted'})


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


@admin_bp.route('/users/<int:user_id>/activity')
@login_required
@admin_required
def user_activity(user_id):
    """View detailed user activity with pagination"""
    from models.submission import Solve, Submission
    from models.challenge import Challenge
    from models.hint import HintUnlock
    from datetime import datetime
    
    user = User.query.get_or_404(user_id)
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # Get all solves with challenges
    solves_query = db.session.query(Solve, Challenge).outerjoin(
        Challenge, Solve.challenge_id == Challenge.id
    ).filter(
        Solve.user_id == user_id
    ).order_by(Solve.solved_at.desc())
    
    solves_pagination = solves_query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Get hints unlocked by this user
    hints_unlocked = HintUnlock.query.filter_by(user_id=user_id).order_by(HintUnlock.unlocked_at.desc()).all()
    
    # Get total stats
    total_solves = Solve.query.filter_by(user_id=user_id).filter(Solve.challenge_id.isnot(None)).count()
    total_submissions = Submission.query.filter_by(user_id=user_id).count()
    total_hints = len(hints_unlocked)
    total_score = user.get_score()
    
    return render_template('admin/user_activity.html', 
                          user=user,
                          solves_pagination=solves_pagination,
                          hints_unlocked=hints_unlocked,
                          total_solves=total_solves,
                          total_submissions=total_submissions,
                          total_hints=total_hints,
                          total_score=total_score,
                          now=datetime.utcnow())


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


# Notifications management
@admin_bp.route('/notifications', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_notifications():
    """Admin page to create and send notifications to all users"""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        body = request.form.get('body', '').strip()

        if not title or not body:
            flash('Title and body are required to send a notification', 'error')
            return redirect(url_for('admin.manage_notifications'))
        # Read play_sound option
        play_sound = request.form.get('play_sound') in ('true', 'on', '1')

        # Create notification record (persist whether recipients should play sound)
        notif = Notification(title=title, body=body, sent_by=current_user.id, play_sound=play_sound)
        db.session.add(notif)
        db.session.commit()

        # Broadcast via websocket
        try:
            WebSocketService.emit_notification(notif.to_dict())
        except Exception as e:
            current_app.logger.exception('Failed to emit notification via websocket')

        flash('Notification sent to all connected users', 'success')
        return redirect(url_for('admin.manage_notifications'))

    # GET: list recent notifications
    notifications = Notification.query.order_by(Notification.created_at.desc()).limit(50).all()
    return render_template('admin/notifications.html', notifications=notifications)

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
        
        # Update decay function
        decay_function = request.form.get('decay_function', 'logarithmic')
        if decay_function in ['logarithmic', 'parabolic']:
            Settings.set('decay_function', decay_function, 'string', 'Dynamic scoring decay function')
        
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


@admin_bp.route('/settings/background-theme', methods=['POST'])
@login_required
@admin_required
def update_background_theme():
    """Update custom background theme"""
    from models.settings import Settings
    import re
    
    try:
        enabled = 'custom_background_enabled' in request.form
        Settings.set('custom_background_enabled', enabled, 'bool', 'Enable custom background theme')
        
        if enabled:
            css = request.form.get('custom_background_css', '').strip()
            
            # Security: Only allow background-related CSS properties
            allowed_properties = [
                'background', 'background-color', 'background-image', 
                'background-size', 'background-position', 'background-repeat',
                'background-attachment', 'animation', '@keyframes'
            ]
            
            # Very basic validation - check if it contains only allowed properties
            # This is a simple check, not a full CSS parser
            if css:
                # Remove comments
                css_clean = re.sub(r'/\*.*?\*/', '', css, flags=re.DOTALL)
                
                # Check for potentially dangerous content
                dangerous_patterns = [
                    r'<script', r'javascript:', r'onerror', r'onload',
                    r'eval\(', r'expression\(', r'import\s+["\']'
                ]
                
                for pattern in dangerous_patterns:
                    if re.search(pattern, css_clean, re.IGNORECASE):
                        flash('Invalid CSS: Potentially dangerous content detected', 'error')
                        return redirect(url_for('admin.settings'))
                
                Settings.set('custom_background_css', css, 'string', 'Custom background CSS')
            else:
                Settings.set('custom_background_css', '', 'string', 'Custom background CSS')
        
        flash('Background theme updated successfully!', 'success')
    except Exception as e:
        flash(f'Error updating background theme: {str(e)}', 'error')
    
    return redirect(url_for('admin.settings'))


@admin_bp.route('/update-system-settings', methods=['POST'])
@login_required
@admin_required
def update_system_settings():
    """Update system settings (timezone and backup frequency)"""
    from models.settings import Settings
    from services.backup_scheduler import backup_scheduler
    
    try:
        # Update timezone
        timezone = request.form.get('timezone', 'UTC')
        Settings.set('timezone', timezone, 'string', 'Platform timezone')
        
        # Update backup frequency
        backup_frequency = request.form.get('backup_frequency', 'disabled')
        old_frequency = Settings.get('backup_frequency', 'disabled')
        Settings.set('backup_frequency', backup_frequency, 'string', 'Automatic backup frequency')
        
        # Clear last auto backup time if disabling backups
        if backup_frequency == 'disabled':
            Settings.set('last_auto_backup', None, 'datetime', 'Last automatic backup timestamp')
        
        # Reschedule backups if frequency changed
        if backup_frequency != old_frequency and backup_scheduler is not None:
            backup_scheduler.reschedule()
        
        flash('System settings updated successfully!', 'success')
    except Exception as e:
        flash(f'Error updating system settings: {str(e)}', 'error')
    
    return redirect(url_for('admin.settings'))


# CTF Control
@admin_bp.route('/ctf-control', methods=['GET', 'POST'])
@login_required
@admin_required
def ctf_control():
    """CTF control panel for scheduling and pausing"""
    from models.settings import Settings
    from datetime import datetime
    import pytz
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'set_times':
            start_time_str = request.form.get('start_time')
            end_time_str = request.form.get('end_time')
            
            # Get platform timezone
            tz_name = Settings.get('timezone', 'UTC')
            try:
                tz = pytz.timezone(tz_name)
            except pytz.UnknownTimeZoneError:
                tz = pytz.UTC
            
            if start_time_str:
                try:
                    # Parse as naive datetime (user input is in platform timezone)
                    start_time_naive = datetime.fromisoformat(start_time_str)
                    # Localize to platform timezone
                    start_time_aware = tz.localize(start_time_naive)
                    # Convert to UTC for storage
                    start_time_utc = start_time_aware.astimezone(pytz.UTC).replace(tzinfo=None)
                    Settings.set('ctf_start_time', start_time_utc, 'datetime', 'CTF start time')
                    flash('CTF start time set successfully!', 'success')
                except ValueError:
                    flash('Invalid start time format', 'error')
            
            if end_time_str:
                try:
                    # Parse as naive datetime (user input is in platform timezone)
                    end_time_naive = datetime.fromisoformat(end_time_str)
                    # Localize to platform timezone
                    end_time_aware = tz.localize(end_time_naive)
                    # Convert to UTC for storage
                    end_time_utc = end_time_aware.astimezone(pytz.UTC).replace(tzinfo=None)
                    Settings.set('ctf_end_time', end_time_utc, 'datetime', 'CTF end time')
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
    import re
    
    challenge_id = request.form.get('challenge_id')
    flag_value = request.form.get('flag_value', '').strip()
    flag_label = request.form.get('flag_label', '').strip()
    unlocks_challenge_id = request.form.get('unlocks_challenge_id')
    points_override = request.form.get('points_override')
    is_case_sensitive = request.form.get('is_case_sensitive', '1') == '1'
    is_regex = request.form.get('is_regex', '0') == '1'
    
    if not challenge_id or not flag_value:
        return jsonify({'success': False, 'message': 'Challenge and flag value are required'}), 400
    
    # Validate challenge exists
    challenge = Challenge.query.get(challenge_id)
    if not challenge:
        return jsonify({'success': False, 'message': 'Challenge not found'}), 404
    
    # For regex flags, validate the pattern
    if is_regex:
        try:
            re.compile(flag_value)
        except re.error as e:
            return jsonify({'success': False, 'message': f'Invalid regex pattern: {str(e)}'}), 400
    
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
        is_case_sensitive=is_case_sensitive,
        is_regex=is_regex
    )
    
    db.session.add(new_flag)
    db.session.commit()
    
    cache_service.invalidate_challenge(challenge_id)
    
    return jsonify({'success': True, 'message': 'Flag added successfully', 'flag': new_flag.to_dict(include_value=True)})


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


# ==================== Flag Abuse Monitoring ====================

@admin_bp.route('/flag-abuse')
@login_required
@admin_required
def flag_abuse():
    """Flag abuse attempts monitoring page"""
    from models.flag_abuse import FlagAbuseAttempt
    from models.challenge import Challenge
    from models.user import User
    from models.team import Team
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    # Filters
    challenge_id = request.args.get('challenge_id', type=int)
    team_id = request.args.get('team_id', type=int)
    user_id = request.args.get('user_id', type=int)
    severity = request.args.get('severity', type=str)
    
    # Build query
    query = FlagAbuseAttempt.query
    
    if challenge_id:
        query = query.filter_by(challenge_id=challenge_id)
    if team_id:
        query = query.filter_by(team_id=team_id)
    if user_id:
        query = query.filter_by(user_id=user_id)
    if severity:
        query = query.filter_by(severity=severity)
    
    # Order by most recent first
    query = query.order_by(FlagAbuseAttempt.timestamp.desc())
    
    # Paginate
    attempts = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Get filter options
    challenges = Challenge.query.order_by(Challenge.name).all()
    teams = Team.query.order_by(Team.name).all()
    
    # Get statistics
    total_attempts = FlagAbuseAttempt.query.count()
    attempts_today = FlagAbuseAttempt.query.filter(
        FlagAbuseAttempt.timestamp >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    ).count()
    unique_users = db.session.query(FlagAbuseAttempt.user_id).distinct().count()
    unique_teams = db.session.query(FlagAbuseAttempt.team_id).filter(
        FlagAbuseAttempt.team_id.isnot(None)
    ).distinct().count()
    
    # Get repeat offenders (teams with multiple attempts)
    repeat_offenders = FlagAbuseAttempt.get_repeat_offenders(limit=10, min_attempts=3)
    
    # Count by severity
    severity_counts = {
        'warning': FlagAbuseAttempt.query.filter_by(severity='warning').count(),
        'suspicious': FlagAbuseAttempt.query.filter_by(severity='suspicious').count(),
        'critical': FlagAbuseAttempt.query.filter_by(severity='critical').count()
    }
    
    return render_template('admin/flag_abuse.html',
        attempts=attempts.items,
        pagination=attempts,
        challenges=challenges,
        teams=teams,
        total_attempts=total_attempts,
        attempts_today=attempts_today,
        unique_users=unique_users,
        unique_teams=unique_teams,
        repeat_offenders=repeat_offenders,
        severity_counts=severity_counts,
        filters={
            'challenge_id': challenge_id,
            'team_id': team_id,
            'user_id': user_id,
            'severity': severity
        }
    )


@admin_bp.route('/flag-abuse/<int:attempt_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_flag_abuse_attempt(attempt_id):
    """Delete a flag abuse attempt record"""
    from models.flag_abuse import FlagAbuseAttempt
    
    attempt = FlagAbuseAttempt.query.get_or_404(attempt_id)
    db.session.delete(attempt)
    db.session.commit()
    
    flash('Flag abuse record deleted successfully', 'success')
    return redirect(url_for('admin.flag_abuse'))


@admin_bp.route('/flag-abuse/clear-all', methods=['POST'])
@login_required
@admin_required
def clear_all_flag_abuse():
    """Clear all flag abuse attempt records"""
    from models.flag_abuse import FlagAbuseAttempt
    
    count = FlagAbuseAttempt.query.delete()
    db.session.commit()
    
    flash(f'Cleared {count} flag abuse records', 'success')
    return redirect(url_for('admin.flag_abuse'))


# ==================== Backup Management ====================

@admin_bp.route('/backups')
@login_required
@admin_required
def backups():
    """Backup management page"""
    return render_template('admin/backups.html')


@admin_bp.route('/backups/api/list')
@login_required
@admin_required
def list_backups():
    """List all available backups (stored in uploads directory)"""
    import json
    import os
    from pathlib import Path
    from datetime import datetime
    
    try:
        # Store backups in the uploads directory under 'backups' folder
        backup_dir = Path(current_app.config.get('UPLOAD_FOLDER', 'static/uploads')) / 'backups'
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        backups = []
        
        if backup_dir.exists():
            for backup_file in sorted(backup_dir.glob('backup_*.sql.gz'), reverse=True):
                backup_name = backup_file.stem.replace('.sql', '')  # Remove .sql from name
                
                # Try to read metadata if it exists
                metadata_file = backup_file.with_suffix('.json')
                if metadata_file.exists():
                    try:
                        with open(metadata_file, 'r') as f:
                            metadata = json.load(f)
                            backups.append(metadata)
                    except json.JSONDecodeError:
                        # Use file modification time as fallback, convert to ISO format
                        timestamp = datetime.fromtimestamp(backup_file.stat().st_mtime).isoformat()
                        backups.append({
                            'backup_name': backup_name,
                            'timestamp': timestamp,
                            'size_mb': round(backup_file.stat().st_size / (1024 * 1024), 2)
                        })
                else:
                    # Use file modification time as fallback, convert to ISO format
                    timestamp = datetime.fromtimestamp(backup_file.stat().st_mtime).isoformat()
                    backups.append({
                        'backup_name': backup_name,
                        'timestamp': timestamp,
                        'size_mb': round(backup_file.stat().st_size / (1024 * 1024), 2)
                    })
        
        return jsonify({'success': True, 'backups': backups})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@admin_bp.route('/backups/api/create', methods=['POST'])
@login_required
@admin_required
def create_backup():
    """Create a manual database backup"""
    import gzip
    import json
    from datetime import datetime
    from pathlib import Path
    
    try:
        # Get database connection info
        db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI')
        
        # Create backup directory
        backup_dir = Path(current_app.config.get('UPLOAD_FOLDER', 'static/uploads')) / 'backups'
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate backup name
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f'backup_{timestamp}'
        backup_file = backup_dir / f'{backup_name}.sql.gz'
        
        # Determine optional components requested (JSON body or form)
        include_uploads = False
        include_redis = False
        try:
            data = request.get_json(silent=True) or {}
            include_uploads = bool(data.get('include_uploads'))
            include_redis = bool(data.get('include_redis'))
        except Exception:
            include_uploads = request.form.get('include_uploads') == 'on'
            include_redis = request.form.get('include_redis') == 'on'

        # Export database to SQL dump
        import pymysql
        from urllib.parse import urlparse
        
        parsed = urlparse(db_uri)
        conn = pymysql.connect(
            host=parsed.hostname,
            port=parsed.port or 3306,
            user=parsed.username,
            password=parsed.password,
            database=parsed.path.lstrip('/')
        )
        
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SHOW TABLES")
        tables = [table[0] for table in cursor.fetchall()]
        
        # Create SQL dump
        sql_dump = []
        sql_dump.append(f"-- Database backup: {backup_name}")
        sql_dump.append(f"-- Timestamp: {datetime.now().isoformat()}")
        sql_dump.append("SET FOREIGN_KEY_CHECKS=0;")
        
        for table in tables:
            # Get CREATE TABLE statement
            cursor.execute(f"SHOW CREATE TABLE `{table}`")
            create_table = cursor.fetchone()[1]
            sql_dump.append(f"\n-- Table: {table}")
            sql_dump.append(f"DROP TABLE IF EXISTS `{table}`;")
            sql_dump.append(create_table + ";")
            
            # Get table data
            cursor.execute(f"SELECT * FROM `{table}`")
            rows = cursor.fetchall()
            
            if rows:
                cursor.execute(f"DESCRIBE `{table}`")
                columns = [col[0] for col in cursor.fetchall()]
                
                for row in rows:
                    values = []
                    for value in row:
                        if value is None:
                            values.append('NULL')
                        elif isinstance(value, (int, float)):
                            values.append(str(value))
                        elif isinstance(value, datetime):
                            values.append(f"'{value.isoformat()}'")
                        else:
                            # Escape single quotes
                            escaped = str(value).replace("'", "''")
                            values.append(f"'{escaped}'")
                    
                    sql_dump.append(f"INSERT INTO `{table}` VALUES ({', '.join(values)});")
        
        sql_dump.append("SET FOREIGN_KEY_CHECKS=1;")
        
        conn.close()
        
        # Write compressed backup
        with gzip.open(backup_file, 'wt', encoding='utf-8') as f:
            f.write('\n'.join(sql_dump))
        
        # Prepare components metadata
        components = {'database': True, 'uploads': False, 'redis': False}
        sizes = {
            'database_mb': round(backup_file.stat().st_size / (1024 * 1024), 2),
            'uploads_mb': 0,
            'redis_mb': 0
        }

        # Include uploads if requested
        if include_uploads:
            try:
                uploads_dir = Path(current_app.config.get('UPLOAD_FOLDER', 'static/uploads'))
                uploads_archive = backup_dir / f"{backup_name}_uploads.tar.gz"
                if uploads_dir.exists():
                    import tarfile
                    with tarfile.open(uploads_archive, 'w:gz') as tar:
                        tar.add(uploads_dir, arcname='uploads')
                    components['uploads'] = True
                    sizes['uploads_mb'] = round(uploads_archive.stat().st_size / (1024 * 1024), 2)
            except Exception as e:
                current_app.logger.warning(f"Failed to include uploads in manual backup: {e}")

        # Include redis snapshot if requested (best-effort)
        if include_redis:
            try:
                import redis as redislib
                redis_url = current_app.config.get('REDIS_URL')
                if redis_url:
                    r = redislib.from_url(redis_url)
                    try:
                        r.bgsave()
                    except Exception:
                        try:
                            r.save()
                        except Exception:
                            pass

                    try:
                        cfg = r.config_get('dir')
                        dirpath = cfg.get('dir') if isinstance(cfg, dict) else None
                        dbfile = r.config_get('dbfilename')
                        filename = dbfile.get('dbfilename') if isinstance(dbfile, dict) else None
                        if dirpath and filename:
                            dump_path = Path(dirpath) / filename
                            if dump_path.exists():
                                import shutil
                                target = backup_dir / f"{backup_name}_redis.rdb"
                                shutil.copy2(dump_path, target)
                                components['redis'] = True
                                sizes['redis_mb'] = round(target.stat().st_size / (1024 * 1024), 2)
                    except Exception:
                        current_app.logger.debug('Could not copy redis dump file; skipping')
            except Exception as e:
                current_app.logger.warning(f"Failed to include redis in manual backup: {e}")

        # Create metadata
        metadata = {
            'backup_name': backup_name,
            'timestamp': datetime.now().isoformat(),
            'database': parsed.path.lstrip('/'),
            'tables': len(tables),
            'size_mb': sizes['database_mb'],
            'components': components,
            'sizes': sizes
        }
        
        metadata_file = backup_dir / f'{backup_name}.json'
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)

        return jsonify({
            'success': True,
            'message': 'Backup created successfully',
            'backup': metadata
        })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@admin_bp.route('/backups/api/restore', methods=['POST'])
@login_required
@admin_required
def restore_backup():
    """Restore from a backup"""
    import gzip
    from pathlib import Path
    
    data = request.get_json()
    backup_name = data.get('backup_name')
    
    if not backup_name or not backup_name.startswith('backup_'):
        return jsonify({'success': False, 'error': 'Invalid backup name'})
    
    try:
        backup_dir = Path(current_app.config.get('UPLOAD_FOLDER', 'static/uploads')) / 'backups'
        backup_file = backup_dir / f'{backup_name}.sql.gz'
        
        if not backup_file.exists():
            return jsonify({'success': False, 'error': 'Backup file not found'})
        
        # Read and execute SQL dump
        import pymysql
        from urllib.parse import urlparse
        
        db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI')
        parsed = urlparse(db_uri)
        
        conn = pymysql.connect(
            host=parsed.hostname,
            port=parsed.port or 3306,
            user=parsed.username,
            password=parsed.password,
            database=parsed.path.lstrip('/'),
            charset='utf8mb4'
        )
        
        cursor = conn.cursor()
        
        # Disable foreign key checks for restore
        cursor.execute('SET FOREIGN_KEY_CHECKS=0')
        
        # Read backup file
        with gzip.open(backup_file, 'rt', encoding='utf-8') as f:
            sql_content = f.read()
        
        # Parse SQL to extract only INSERT statements (skip DROP/CREATE)
        # We only want to restore DATA, not recreate table structures
        statements = []
        current_statement = []
        
        for line in sql_content.split('\n'):
            line = line.strip()
            
            # Skip comments and empty lines
            if line.startswith('--') or not line:
                continue
            
            # Skip DROP TABLE and CREATE TABLE statements
            # We only want INSERT statements (data restoration)
            if line.upper().startswith('DROP TABLE') or line.upper().startswith('CREATE TABLE'):
                continue
            
            current_statement.append(line)
            
            # Check if statement is complete (ends with semicolon)
            if line.endswith(';'):
                full_statement = ' '.join(current_statement).strip()
                if full_statement:
                    statements.append(full_statement)
                current_statement = []
        
        # Add any remaining statement
        if current_statement:
            full_statement = ' '.join(current_statement).strip()
            if full_statement and full_statement.endswith(';'):
                statements.append(full_statement)
        
        # Get list of tables to clear
        cursor.execute("SHOW TABLES")
        tables = [table[0] for table in cursor.fetchall()]
        
        # Clear all existing data from tables (DELETE, not DROP)
        tables_cleared = 0
        for table in tables:
            try:
                # Skip system/migration tables if any
                if table in ['alembic_version', 'migrations']:
                    continue
                cursor.execute(f"DELETE FROM `{table}`")
                tables_cleared += 1
            except pymysql.err.Error as e:
                # Some tables might fail, continue with others
                pass
        
        # Execute INSERT statements with proper error handling
        errors = []
        success_count = 0
        
        for i, statement in enumerate(statements):
            try:
                # Only process SET and INSERT statements
                if statement.upper().startswith('SET '):
                    cursor.execute(statement)
                    success_count += 1
                elif statement.upper().startswith('INSERT '):
                    cursor.execute(statement)
                    success_count += 1
                    
            except pymysql.err.Error as e:
                error_msg = f"Statement {i+1}: {str(e)[:100]}"
                errors.append(error_msg)
                # Continue with other statements instead of failing completely
                continue
        
        # Re-enable foreign key checks
        cursor.execute('SET FOREIGN_KEY_CHECKS=1')
        
        conn.commit()
        conn.close()
        
        # Clear all caches
        from services.cache import cache_service
        cache_service.clear_all()
        
        if errors and success_count == 0:
            return jsonify({
                'success': False,
                'error': f'Restore failed. No data could be restored. Errors: {"; ".join(errors[:3])}'
            })
        elif errors:
            return jsonify({
                'success': True,
                'message': f'Backup restored! Cleared {tables_cleared} tables and inserted {success_count} records. Some minor errors occurred but restore succeeded. All caches cleared.',
                'warnings': errors[:5]  # Show first 5 errors
            })
        else:
            return jsonify({
                'success': True,
                'message': f'Backup restored successfully! Cleared {tables_cleared} tables and inserted {success_count} records. All caches cleared.'
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@admin_bp.route('/backups/api/delete', methods=['POST'])
@login_required
@admin_required
def delete_backup():
    """Delete a backup"""
    from pathlib import Path
    
    data = request.get_json()
    backup_name = data.get('backup_name')
    
    if not backup_name or not backup_name.startswith('backup_'):
        return jsonify({'success': False, 'error': 'Invalid backup name'})
    
    try:
        backup_dir = Path(current_app.config.get('UPLOAD_FOLDER', 'static/uploads')) / 'backups'
        backup_file = backup_dir / f'{backup_name}.sql.gz'
        metadata_file = backup_dir / f'{backup_name}.json'
        
        # Delete files
        if backup_file.exists():
            backup_file.unlink()
        if metadata_file.exists():
            metadata_file.unlink()
        
        return jsonify({'success': True, 'message': 'Backup deleted successfully'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@admin_bp.route('/backups/api/download/<backup_name>')
@login_required
@admin_required
def download_backup(backup_name):
    """Download a backup file"""
    from flask import send_file
    from pathlib import Path
    
    if not backup_name.startswith('backup_'):
        flash('Invalid backup name', 'error')
        return redirect(url_for('admin.backups'))
    
    try:
        backup_dir = Path(current_app.config.get('UPLOAD_FOLDER', 'static/uploads')) / 'backups'
        backup_file = backup_dir / f'{backup_name}.sql.gz'
        
        if not backup_file.exists():
            flash('Backup file not found', 'error')
            return redirect(url_for('admin.backups'))
        
        return send_file(
            backup_file,
            as_attachment=True,
            download_name=f'{backup_name}.sql.gz',
            mimetype='application/gzip'
        )
        
    except Exception as e:
        flash(f'Download failed: {str(e)}', 'error')
        return redirect(url_for('admin.backups'))


@admin_bp.route('/backups/api/upload', methods=['POST'])
@login_required
@admin_required
def upload_backup():
    """Upload a backup file for restoration"""
    from pathlib import Path
    from datetime import datetime
    import json
    
    try:
        if 'backup_file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'})
        
        file = request.files['backup_file']
        
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})
        
        if not file.filename.endswith('.sql.gz'):
            return jsonify({'success': False, 'error': 'Invalid file type. Must be .sql.gz'})
        
        # Save to backups directory
        backup_dir = Path(current_app.config.get('UPLOAD_FOLDER', 'static/uploads')) / 'backups'
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate name if not already in backup format
        if file.filename.startswith('backup_'):
            backup_name = file.filename.replace('.sql.gz', '')
        else:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f'backup_uploaded_{timestamp}'
        
        backup_file = backup_dir / f'{backup_name}.sql.gz'
        file.save(backup_file)
        
        # Create metadata
        metadata = {
            'backup_name': backup_name,
            'timestamp': datetime.now().isoformat(),
            'uploaded': True,
            'original_filename': file.filename,
            'size_mb': backup_file.stat().st_size / (1024 * 1024)
        }
        
        metadata_file = backup_dir / f'{backup_name}.json'
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return jsonify({
            'success': True,
            'message': 'Backup uploaded successfully',
            'backup': metadata
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ==================== Docker Container Management ====================

@admin_bp.route('/docker/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def docker_settings():
    """Configure Docker connection and settings"""
    from models.settings import DockerSettings
    
    settings = DockerSettings.get_config()
    
    if request.method == 'POST':
        # Update basic settings
        settings.hostname = request.form.get('hostname') or None
        settings.tls_enabled = request.form.get('tls_enabled') == 'true'
        settings.max_containers_per_user = int(request.form.get('max_containers_per_user', 1))
        settings.container_lifetime_minutes = int(request.form.get('container_lifetime_minutes', 15))
        settings.revert_cooldown_minutes = int(request.form.get('revert_cooldown_minutes', 5))
        settings.port_range_start = int(request.form.get('port_range_start', 30000))
        settings.port_range_end = int(request.form.get('port_range_end', 60000))
        settings.auto_cleanup_on_solve = request.form.get('auto_cleanup_on_solve') == 'true'
        settings.cleanup_stale_containers = request.form.get('cleanup_stale_containers') == 'true'
        settings.stale_container_hours = int(request.form.get('stale_container_hours', 2))
        settings.allowed_repositories = request.form.get('allowed_repositories', '').strip()
        
        # Handle certificate uploads
        if 'ca_cert' in request.files:
            ca_file = request.files['ca_cert']
            if ca_file and ca_file.filename:
                settings.ca_cert = ca_file.read().decode('utf-8')
        
        if 'client_cert' in request.files:
            cert_file = request.files['client_cert']
            if cert_file and cert_file.filename:
                settings.client_cert = cert_file.read().decode('utf-8')
        
        if 'client_key' in request.files:
            key_file = request.files['client_key']
            if key_file and key_file.filename:
                settings.client_key = key_file.read().decode('utf-8')
        
        # If TLS disabled, clear certificates
        if not settings.tls_enabled:
            settings.ca_cert = None
            settings.client_cert = None
            settings.client_key = None
        
        db.session.commit()
        
        # Reinitialize Docker client
        from services.container_manager import container_orchestrator
        container_orchestrator._init_docker_client()
        
        flash('Docker settings updated successfully', 'success')
        return redirect(url_for('admin.docker_settings'))
    
    return render_template('admin/docker_settings.html', docker_settings=settings)


@admin_bp.route('/docker/status')
@login_required
@admin_required
def docker_status():
    """View all active containers"""
    from models.container import ContainerInstance
    
    # Get all containers
    containers = ContainerInstance.query.filter(
        ContainerInstance.status.in_(['starting', 'running'])
    ).order_by(ContainerInstance.started_at.desc()).all()
    
    # Enrich with user/team/challenge info
    container_data = []
    for c in containers:
        container_data.append({
            'id': c.id,
            'user': c.user.username if c.user else 'Unknown',
            'team': c.team.name if c.team else 'N/A',
            'challenge': c.challenge.name if c.challenge else 'Unknown',
            'container_id': c.container_id[:12] if c.container_id else 'N/A',
            'host_port': c.host_port,
            'status': c.status,
            'started_at': c.started_at,
            'expires_at': c.expires_at,
            'remaining_time': c.get_remaining_time() if c.expires_at else 'N/A'
        })
    
    return render_template('admin/docker_status.html', containers=container_data)


@admin_bp.route('/docker/containers/<int:container_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_container(container_id):
    """Admin force-delete a container"""
    from models.container import ContainerInstance
    from services.container_manager import container_orchestrator
    import docker
    
    try:
        container = ContainerInstance.query.get_or_404(container_id)
        
        # Stop Docker container
        try:
            if container_orchestrator.docker_client:
                docker_container = container_orchestrator.docker_client.containers.get(container.container_id)
                docker_container.stop(timeout=10)
                docker_container.remove()
        except docker.errors.NotFound:
            pass  # Already removed
        except Exception as e:
            current_app.logger.error(f"Failed to stop container: {e}")
        
        # Update database
        container.status = 'stopped'
        container.stopped_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Container deleted successfully'
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin_bp.route('/docker/containers/delete-all', methods=['POST'])
@login_required
@admin_required
def delete_all_containers():
    """Delete all running containers"""
    from models.container import ContainerInstance
    from services.container_manager import container_orchestrator
    import docker
    
    try:
        containers = ContainerInstance.query.filter(
            ContainerInstance.status.in_(['starting', 'running'])
        ).all()
        
        deleted_count = 0
        for container in containers:
            try:
                if container_orchestrator.docker_client:
                    docker_container = container_orchestrator.docker_client.containers.get(container.container_id)
                    docker_container.stop(timeout=10)
                    docker_container.remove()
            except docker.errors.NotFound:
                pass
            except Exception as e:
                current_app.logger.error(f"Failed to stop container {container.id}: {e}")
            
            container.status = 'stopped'
            container.stopped_at = datetime.utcnow()
            deleted_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Deleted {deleted_count} containers'
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin_bp.route('/docker/images')
@login_required
@admin_required
def list_docker_images():
    """List available Docker images"""
    from services.container_manager import container_orchestrator
    
    result = container_orchestrator.list_available_images()
    return jsonify(result)

