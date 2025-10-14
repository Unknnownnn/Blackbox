from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from models import db
from models.challenge import Challenge
from models.submission import Submission, Solve
from models.file import ChallengeFile
from services.scoring import ScoringService
from services.cache import cache_service
from services.websocket import WebSocketService
from datetime import datetime

challenges_bp = Blueprint('challenges', __name__, url_prefix='/challenges')

@challenges_bp.route('/')
@login_required
def list_challenges():
    """List all visible challenges"""
    from models.settings import Settings
    
    # Check if team is required globally
    require_team = Settings.get('require_team_for_challenges', default=False, type='bool')
    team = current_user.get_team()
    
    # If team is required globally and user is not in a team (and not admin), show message
    if require_team and not team and not current_user.is_admin:
        flash('You must join a team to view and solve challenges. Please join or create a team first.', 'warning')
        return redirect(url_for('teams.list_teams'))
    
    challenges = Challenge.query.filter_by(is_visible=True).all()
    
    # Organize challenges by category
    categories = {}
    for challenge in challenges:
        # Check if this specific challenge requires a team
        if challenge.requires_team and not team and not current_user.is_admin:
            continue  # Skip this challenge if it requires team and user has no team
        
        # Check if challenge is unlocked for user
        if not current_user.is_admin:
            if not challenge.is_unlocked_for_user(current_user.id, team.id if team else None):
                continue  # Skip hidden/locked challenges
        
        if challenge.category not in categories:
            categories[challenge.category] = []
        
        # Check if solved
        if team:
            solved = challenge.is_solved_by_team(team.id)
        else:
            solved = challenge.is_solved_by_user(current_user.id)
        
        challenge_data = challenge.to_dict(include_flag=False)
        challenge_data['solved'] = solved
        challenge_data['requires_team'] = challenge.requires_team
        
        # Add prerequisite info if locked
        if challenge.unlock_mode == 'prerequisite':
            missing = challenge.get_missing_prerequisites(current_user.id, team.id if team else None)
            if missing:
                challenge_data['locked'] = True
                challenge_data['missing_prerequisites'] = [c.name for c in missing]
        
        categories[challenge.category].append(challenge_data)
    
    return render_template('challenges.html', categories=categories, team=team)


@challenges_bp.route('/<int:challenge_id>')
@login_required
def view_challenge(challenge_id):
    """View challenge details"""
    from models.settings import Settings
    
    challenge = Challenge.query.get_or_404(challenge_id)
    
    if not challenge.is_visible and not current_user.is_admin:
        flash('Challenge not found', 'error')
        return redirect(url_for('challenges.list_challenges'))
    
    # Get user's team
    team = current_user.get_team()
    
    # Check if team is required (either globally or per-challenge)
    require_team_global = Settings.get('require_team_for_challenges', default=False, type='bool')
    
    if (require_team_global or challenge.requires_team) and not team and not current_user.is_admin:
        flash('You must be in a team to view this challenge. Please join or create a team first.', 'warning')
        return redirect(url_for('teams.list_teams'))
    
    # Check if solved
    if team:
        solved = challenge.is_solved_by_team(team.id)
    else:
        solved = challenge.is_solved_by_user(current_user.id)
    
    challenge_data = challenge.to_dict(include_flag=False)
    challenge_data['solved'] = solved
    challenge_data['requires_team'] = challenge.requires_team
    
    # Get challenge files
    challenge_files = ChallengeFile.query.filter_by(challenge_id=challenge_id).all()
    files_data = [f.to_dict() for f in challenge_files]
    
    # Get hints
    from models.hint import Hint
    hints = Hint.query.filter_by(challenge_id=challenge_id).order_by(Hint.order).all()
    hints_data = []
    for hint in hints:
        # Check if unlocked
        if team:
            unlocked = hint.is_unlocked_by_team(team.id)
        else:
            unlocked = hint.is_unlocked_by_user(current_user.id)
        
        hint_info = {
            'id': hint.id,
            'cost': hint.cost,
            'order': hint.order,
            'unlocked': unlocked,
        }
        
        if unlocked or current_user.is_admin:
            hint_info['content'] = hint.content
        
        hints_data.append(hint_info)
    
    # Check if challenge has branching (multiple paths)
    from models.branching import ChallengeFlag, ChallengeUnlock
    challenge_flags = ChallengeFlag.query.filter_by(challenge_id=challenge_id).all()
    has_branching = any(flag.unlocks_challenge_id is not None for flag in challenge_flags)
    challenge_data['has_branching'] = has_branching
    
    # Get unlocked paths for this user/team
    unlocked_paths = []
    if solved and has_branching:
        user_id = current_user.id
        team_id = team.id if team else None
        
        # Find all flags from THIS challenge that unlock other challenges
        unlocking_flags = ChallengeFlag.query.filter(
            ChallengeFlag.challenge_id == challenge_id,
            ChallengeFlag.unlocks_challenge_id.isnot(None)
        ).all()
        
        # For each unlocking flag, check if user has unlocked it
        for flag in unlocking_flags:
            unlock = ChallengeUnlock.query.filter(
                ChallengeUnlock.unlocked_by_flag_id == flag.id,
                db.or_(
                    ChallengeUnlock.user_id == user_id,
                    ChallengeUnlock.team_id == team_id
                )
            ).first()
            
            if unlock:
                unlocked_challenge = Challenge.query.get(flag.unlocks_challenge_id)
                if unlocked_challenge:
                    unlocked_paths.append({
                        'challenge_name': unlocked_challenge.name,
                        'category': unlocked_challenge.category,
                        'flag_label': flag.flag_label if flag.flag_label else 'primary flag'
                    })
    
    challenge_data['unlocked_paths'] = unlocked_paths
    
    return render_template('challenge_detail.html', 
                          challenge=challenge_data, 
                          files=files_data,
                          hints=hints_data,
                          team=team)


@challenges_bp.route('/<int:challenge_id>/submit', methods=['POST'])
@login_required
def submit_flag(challenge_id):
    """Submit a flag for a challenge"""
    from models.settings import Settings
    
    # Check CTF status
    ctf_status = Settings.get_ctf_status()
    
    if ctf_status == 'not_started':
        start_time = Settings.get('ctf_start_time')
        return jsonify({
            'success': False, 
            'message': f'CTF has not started yet. Starts at: {start_time.strftime("%Y-%m-%d %H:%M UTC") if start_time else "TBD"}'
        }), 403
    
    if ctf_status == 'ended':
        end_time = Settings.get('ctf_end_time')
        return jsonify({
            'success': False, 
            'message': f'CTF has ended. Ended at: {end_time.strftime("%Y-%m-%d %H:%M UTC") if end_time else "Unknown"}'
        }), 403
    
    if ctf_status == 'paused':
        return jsonify({
            'success': False, 
            'message': 'CTF is currently paused by administrators. Please wait for it to resume.'
        }), 403
    
    challenge = Challenge.query.get_or_404(challenge_id)
    
    if not challenge.is_visible and not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Challenge not found'}), 404
    
    # Check if challenge is enabled
    if not challenge.is_enabled and not current_user.is_admin:
        return jsonify({
            'success': False, 
            'message': 'This challenge is temporarily disabled. Please try again later.'
        }), 403
    
    # Get user's team
    team = current_user.get_team()
    team_id = team.id if team else None
    
    # Check if team is required for this challenge
    if challenge.requires_team and not team_id and not current_user.is_admin:
        return jsonify({
            'success': False, 
            'message': 'You must be in a team to solve this challenge. Please join or create a team first.'
        }), 403
    
    # Check global team requirement setting
    if Settings.get('require_team_for_challenges', default=False, type='bool') and not team_id and not current_user.is_admin:
        return jsonify({
            'success': False, 
            'message': 'You must be in a team to solve challenges. Please join or create a team first.'
        }), 403
    
    submitted_flag = request.form.get('flag', '').strip()
    
    if not submitted_flag:
        return jsonify({'success': False, 'message': 'Please enter a flag'}), 400
    
    # Get user's team
    team = current_user.get_team()
    team_id = team.id if team else None
    
    # Check if already solved (by user or team)
    if team:
        already_solved = challenge.is_solved_by_team(team_id)
    else:
        already_solved = challenge.is_solved_by_user(current_user.id)
    
    # Check if this challenge has branching flags (allows re-submission for different paths)
    from models.branching import ChallengeFlag
    challenge_flags = ChallengeFlag.query.filter_by(challenge_id=challenge_id).all()
    has_branching = any(flag.unlocks_challenge_id is not None for flag in challenge_flags)
    
    # If already solved and challenge has no branching, reject submission
    if already_solved and not has_branching:
        return jsonify({'success': False, 'message': 'This challenge has already been solved'}), 400
    
    # Check max attempts limit (0 means unlimited)
    if challenge.max_attempts and challenge.max_attempts > 0:
        if team_id:
            # Count team's attempts for this challenge
            team_attempts = Submission.query.filter_by(
                challenge_id=challenge_id,
                team_id=team_id
            ).count()
            
            if team_attempts >= challenge.max_attempts:
                return jsonify({
                    'success': False,
                    'message': f'Maximum attempts ({challenge.max_attempts}) reached for this challenge'
                }), 400
        else:
            # Count user's attempts
            user_attempts = Submission.query.filter_by(
                challenge_id=challenge_id,
                user_id=current_user.id
            ).count()
            
            if user_attempts >= challenge.max_attempts:
                return jsonify({
                    'success': False,
                    'message': f'Maximum attempts ({challenge.max_attempts}) reached for this challenge'
                }), 400
    
    # Rate limiting check (prevent brute force)
    rate_limit_key = f'submissions:{current_user.id}:{challenge_id}'
    is_allowed, remaining = cache_service.check_rate_limit(rate_limit_key, limit=10, window=60)
    
    if not is_allowed:
        return jsonify({
            'success': False,
            'message': 'Too many attempts. Please wait before trying again.'
        }), 429
    
    # Check the flag
    matched_flag = challenge.check_flag(submitted_flag)
    is_correct = matched_flag is not None
    
    # Create submission record
    submission = Submission(
        user_id=current_user.id,
        challenge_id=challenge_id,
        team_id=team_id,
        submitted_flag=submitted_flag,
        is_correct=is_correct,
        ip_address=request.remote_addr
    )
    db.session.add(submission)
    
    if is_correct:
        # Calculate points at time of solve
        points = challenge.get_current_points()
        
        # Check if flag has a points override
        if hasattr(matched_flag, 'points_override') and matched_flag.points_override:
            points = matched_flag.points_override
        
        # Create solve record - marks challenge as solved for entire team
        solve = Solve(
            user_id=current_user.id,
            challenge_id=challenge_id,
            flag_id=matched_flag.id if hasattr(matched_flag, 'id') else None,
            team_id=team_id,
            points_earned=points
        )
        db.session.add(solve)
        
        # Handle challenge unlocking via flags
        from models.branching import ChallengeUnlock
        unlocked_challenges = []
        
        if hasattr(matched_flag, 'unlocks_challenge_id') and matched_flag.unlocks_challenge_id:
            # This flag unlocks another challenge
            unlock_record = ChallengeUnlock(
                user_id=current_user.id,
                team_id=team_id,
                challenge_id=matched_flag.unlocks_challenge_id,
                unlocked_by_flag_id=matched_flag.id
            )
            db.session.add(unlock_record)
            
            # Get the unlocked challenge details
            unlocked_challenge = Challenge.query.get(matched_flag.unlocks_challenge_id)
            if unlocked_challenge:
                unlocked_challenges.append({
                    'id': unlocked_challenge.id,
                    'name': unlocked_challenge.name,
                    'category': unlocked_challenge.category
                })
        
        # Award points to team (if in team) or user
        if team:
            team.score = team.score + points if hasattr(team, 'score') and team.score else points
        else:
            current_user.score = current_user.score + points if current_user.score else points
        
        db.session.commit()
        
        # Invalidate caches
        cache_service.invalidate_scoreboard()
        cache_service.invalidate_challenge(challenge_id)
        if team_id:
            cache_service.invalidate_team(team_id)
        else:
            cache_service.invalidate_user(current_user.id)
        
        # Emit WebSocket events for live updates
        solve_data = {
            'user': current_user.username,
            'team': team.name if team else None,
            'challenge': challenge.name,
            'category': challenge.category,
            'points': points,
            'timestamp': datetime.utcnow().isoformat()
        }
        WebSocketService.emit_new_solve(solve_data)
        
        # Update challenge points (may have changed)
        new_points = challenge.get_current_points()
        if new_points != points:
            WebSocketService.emit_challenge_update({
                'id': challenge.id,
                'name': challenge.name,
                'points': new_points
            })
        
        # Send updated scoreboard
        scoreboard = ScoringService.get_scoreboard(team_based=True, limit=50)
        cache_service.set_scoreboard(scoreboard)
        WebSocketService.emit_scoreboard_update(scoreboard)
        
        message = 'Correct flag! Challenge solved!'
        if team:
            message += f' Points awarded to team "{team.name}".'
        
        # Add info about unlocked challenges
        response_data = {
            'success': True,
            'message': message,
            'points': points
        }
        
        if unlocked_challenges:
            unlocked_names = ', '.join([c['name'] for c in unlocked_challenges])
            response_data['unlocked_challenges'] = unlocked_challenges
            response_data['message'] += f' New challenge(s) unlocked: {unlocked_names}!'
        
        return jsonify(response_data)
    else:
        db.session.commit()
        
        # Calculate remaining attempts if limited
        attempts_remaining = None
        if challenge.max_attempts and challenge.max_attempts > 0:
            if team_id:
                attempts_used = Submission.query.filter_by(
                    challenge_id=challenge_id,
                    team_id=team_id
                ).count()
            else:
                attempts_used = Submission.query.filter_by(
                    challenge_id=challenge_id,
                    user_id=current_user.id
                ).count()
            attempts_remaining = challenge.max_attempts - attempts_used
        
        response = {
            'success': False,
            'message': 'Incorrect flag'
        }
        
        if attempts_remaining is not None:
            response['attempts_remaining'] = attempts_remaining
            if attempts_remaining > 0:
                response['message'] += f' ({attempts_remaining} attempts remaining)'
        
        return jsonify(response), 400


@challenges_bp.route('/<int:challenge_id>/explore', methods=['POST'])
@login_required
def explore_flag(challenge_id):
    """Submit an additional flag for an already-solved challenge to unlock more paths (no points awarded)"""
    from models.settings import Settings
    from models.branching import ChallengeFlag, ChallengeUnlock
    
    # Check CTF status
    ctf_status = Settings.get_ctf_status()
    
    if ctf_status == 'not_started':
        start_time = Settings.get('ctf_start_time')
        return jsonify({
            'success': False, 
            'message': f'CTF has not started yet. Starts at: {start_time.strftime("%Y-%m-%d %H:%M UTC") if start_time else "TBD"}'
        }), 403
    
    if ctf_status == 'ended':
        end_time = Settings.get('ctf_end_time')
        return jsonify({
            'success': False, 
            'message': f'CTF has ended. Ended at: {end_time.strftime("%Y-%m-%d %H:%M UTC") if end_time else "Unknown"}'
        }), 403
    
    if ctf_status == 'paused':
        return jsonify({
            'success': False, 
            'message': 'CTF is currently paused by administrators. Please wait for it to resume.'
        }), 403
    
    challenge = Challenge.query.get_or_404(challenge_id)
    
    if not challenge.is_visible and not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Challenge not found'}), 404
    
    # Get user's team
    team = current_user.get_team()
    team_id = team.id if team else None
    
    # Check if already solved (must be solved to explore)
    if team:
        already_solved = challenge.is_solved_by_team(team_id)
    else:
        already_solved = challenge.is_solved_by_user(current_user.id)
    
    if not already_solved:
        return jsonify({
            'success': False, 
            'message': 'You must solve this challenge first before exploring additional paths'
        }), 403
    
    # Check if this challenge has branching flags
    challenge_flags = ChallengeFlag.query.filter_by(challenge_id=challenge_id).all()
    has_branching = any(flag.unlocks_challenge_id is not None for flag in challenge_flags)
    
    if not has_branching:
        return jsonify({
            'success': False, 
            'message': 'This challenge has no additional paths to explore'
        }), 400
    
    submitted_flag = request.form.get('flag', '').strip()
    
    if not submitted_flag:
        return jsonify({'success': False, 'message': 'Please enter a flag'}), 400
    
    # Rate limiting check (prevent brute force)
    rate_limit_key = f'explore:{current_user.id}:{challenge_id}'
    is_allowed, remaining = cache_service.check_rate_limit(rate_limit_key, limit=10, window=60)
    
    if not is_allowed:
        return jsonify({
            'success': False,
            'message': 'Too many attempts. Please wait before trying again.'
        }), 429
    
    # Check the flag
    matched_flag = challenge.check_flag(submitted_flag)
    
    if not matched_flag:
        return jsonify({'success': False, 'message': 'Incorrect flag'}), 400
    
    # Check if this specific flag unlocks anything
    if not hasattr(matched_flag, 'unlocks_challenge_id') or not matched_flag.unlocks_challenge_id:
        return jsonify({
            'success': False, 
            'message': 'This flag does not unlock any additional paths'
        }), 400
    
    # Check if this path was already unlocked
    existing_unlock = ChallengeUnlock.query.filter(
        ChallengeUnlock.unlocked_by_flag_id == matched_flag.id,
        db.or_(
            ChallengeUnlock.user_id == current_user.id,
            ChallengeUnlock.team_id == team_id
        )
    ).first()
    
    if existing_unlock:
        return jsonify({
            'success': False, 
            'message': 'You have already unlocked this path'
        }), 400
    
    # Create unlock record (no points, no solve record - just unlocking)
    unlock_record = ChallengeUnlock(
        user_id=current_user.id,
        team_id=team_id,
        challenge_id=matched_flag.unlocks_challenge_id,
        unlocked_by_flag_id=matched_flag.id
    )
    db.session.add(unlock_record)
    
    # Get the unlocked challenge details
    unlocked_challenge = Challenge.query.get(matched_flag.unlocks_challenge_id)
    
    # Optionally auto-configure the unlocked challenge to be visible
    if unlocked_challenge and unlocked_challenge.unlock_mode == 'flag_unlock':
        unlocked_challenge.is_hidden = False
    
    db.session.commit()
    
    # Invalidate caches
    cache_service.invalidate_challenge(challenge_id)
    cache_service.invalidate_challenge(matched_flag.unlocks_challenge_id)
    
    response_data = {
        'success': True,
        'message': 'Correct flag! New path unlocked!',
        'unlocked_challenges': []
    }
    
    if unlocked_challenge:
        response_data['unlocked_challenges'].append({
            'id': unlocked_challenge.id,
            'name': unlocked_challenge.name,
            'category': unlocked_challenge.category
        })
    
    return jsonify(response_data)


@challenges_bp.route('/solves/<int:challenge_id>')
@login_required
def challenge_solves(challenge_id):
    """Get list of teams/users who solved a challenge"""
    challenge = Challenge.query.get_or_404(challenge_id)
    
    solves = Solve.query.filter_by(challenge_id=challenge_id)\
        .order_by(Solve.solved_at.asc()).all()
    
    solve_list = []
    for solve in solves:
        if solve.team_id:
            team = solve.team
            solve_list.append({
                'name': team.name,
                'type': 'team',
                'solved_at': solve.solved_at.isoformat(),
                'points': solve.points_earned
            })
        else:
            user = solve.user
            solve_list.append({
                'name': user.username,
                'type': 'user',
                'solved_at': solve.solved_at.isoformat(),
                'points': solve.points_earned
            })
    
    return jsonify({
        'challenge': challenge.name,
        'solves': solve_list
    })
