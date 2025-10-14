from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from models import db
from models.team import Team
from models.user import User
from services.scoring import ScoringService

teams_bp = Blueprint('teams', __name__, url_prefix='/teams')

@teams_bp.route('/')
@login_required
def list_teams():
    """List all teams"""
    teams = Team.query.filter_by(is_active=True).all()
    
    teams_data = [team.to_dict() for team in teams]
    
    return render_template('teams.html', teams=teams_data, user_team_id=current_user.team_id)


@teams_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_team():
    """Create a new team"""
    if current_user.team_id:
        flash('You are already in a team', 'error')
        return redirect(url_for('teams.view_team', team_id=current_user.team_id))
    
    if request.method == 'POST':
        team_name = request.form.get('team_name')
        affiliation = request.form.get('affiliation')
        country = request.form.get('country')
        password = request.form.get('password')  # Deprecated but kept for backward compatibility
        
        if not team_name:
            flash('Team name is required', 'error')
            return render_template('create_team.html')
        
        # Check if team name already exists
        if Team.query.filter_by(name=team_name).first():
            flash('Team name already taken', 'error')
            return render_template('create_team.html')
        
        # Generate unique invite code
        invite_code = Team.generate_invite_code()
        
        # Create team
        team = Team(
            name=team_name,
            invite_code=invite_code,
            affiliation=affiliation,
            country=country,
            captain_id=current_user.id
        )
        if password:
            team.set_password(password)
        
        db.session.add(team)
        db.session.flush()  # Get team ID
        
        # Add creator as team member and captain
        current_user.team_id = team.id
        current_user.is_team_captain = True
        
        db.session.commit()
        
        flash(f'Team "{team_name}" created successfully! Share your invite code: {invite_code}', 'success')
        return redirect(url_for('teams.view_team', team_id=team.id))
    
    return render_template('create_team.html')


@teams_bp.route('/<int:team_id>')
@login_required
def view_team(team_id):
    """View team details"""
    team = Team.query.get_or_404(team_id)
    
    members = team.get_members()
    progress = ScoringService.get_team_progress(team_id)
    
    is_member = current_user.team_id == team_id
    is_captain = current_user.id == team.captain_id
    
    # Include invite code only for team members
    team_data = team.to_dict(include_members=True, include_invite_code=is_member)
    
    return render_template('team_detail.html', 
                          team=team_data,
                          members=members,
                          progress=progress,
                          is_member=is_member,
                          is_captain=is_captain)


@teams_bp.route('/join', methods=['GET', 'POST'])
@login_required
def join_team_by_code():
    """Join a team using invite code"""
    if current_user.team_id:
        flash('You are already in a team', 'error')
        return redirect(url_for('teams.view_team', team_id=current_user.team_id))
    
    if request.method == 'POST':
        invite_code = request.form.get('invite_code', '').strip().upper()
        
        if not invite_code:
            flash('Please enter an invite code', 'error')
            return render_template('join_team.html')
        
        # Find team by invite code
        team = Team.query.filter_by(invite_code=invite_code).first()
        
        if not team:
            flash('Invalid invite code', 'error')
            return render_template('join_team.html')
        
        # Check team size limit
        from flask import current_app
        max_size = current_app.config.get('TEAM_SIZE', 4)
        
        if not team.can_join(max_size):
            flash(f'Team is full (max {max_size} members)', 'error')
            return render_template('join_team.html')
        
        # Show confirmation page
        return render_template('join_team.html', 
                             team=team.to_dict(), 
                             invite_code=invite_code,
                             confirm=True)
    
    return render_template('join_team.html')


@teams_bp.route('/join/confirm', methods=['POST'])
@login_required
def confirm_join_team():
    """Confirm joining a team"""
    if current_user.team_id:
        return jsonify({'success': False, 'message': 'You are already in a team'}), 400
    
    invite_code = request.form.get('invite_code', '').strip().upper()
    
    if not invite_code:
        return jsonify({'success': False, 'message': 'Invalid invite code'}), 400
    
    team = Team.query.filter_by(invite_code=invite_code).first()
    
    if not team:
        return jsonify({'success': False, 'message': 'Invalid invite code'}), 404
    
    # Check team size limit again
    from flask import current_app
    max_size = current_app.config.get('TEAM_SIZE', 4)
    
    if not team.can_join(max_size):
        return jsonify({'success': False, 'message': f'Team is full (max {max_size} members)'}), 400
    
    # Add user to team
    current_user.team_id = team.id
    db.session.commit()
    
    flash(f'Successfully joined team "{team.name}"!', 'success')
    return jsonify({
        'success': True,
        'message': f'Successfully joined team "{team.name}"',
        'redirect': url_for('teams.view_team', team_id=team.id)
    })


@teams_bp.route('/<int:team_id>/join', methods=['POST'])
@login_required
def join_team(team_id):
    """Join a team"""
    if current_user.team_id:
        return jsonify({'success': False, 'message': 'You are already in a team'}), 400
    
    team = Team.query.get_or_404(team_id)
    
    # Check team size limit
    from flask import current_app
    max_size = current_app.config.get('TEAM_SIZE', 4)
    
    if not team.can_join(max_size):
        return jsonify({'success': False, 'message': f'Team is full (max {max_size} members)'}), 400
    
    # Check password if required
    if team.password_hash:
        password = request.form.get('password')
        if not password or not team.check_password(password):
            return jsonify({'success': False, 'message': 'Incorrect team password'}), 403
    
    # Add user to team
    current_user.team_id = team.id
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Successfully joined team "{team.name}"'
    })


@teams_bp.route('/<int:team_id>/leave', methods=['POST'])
@login_required
def leave_team(team_id):
    """Leave a team"""
    if current_user.team_id != team_id:
        return jsonify({'success': False, 'message': 'You are not in this team'}), 400
    
    team = Team.query.get_or_404(team_id)
    
    # Captain cannot leave (must transfer ownership first)
    if current_user.id == team.captain_id:
        return jsonify({
            'success': False,
            'message': 'Team captain must transfer ownership before leaving'
        }), 400
    
    current_user.team_id = None
    current_user.is_team_captain = False
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Left team "{team.name}"'
    })


@teams_bp.route('/<int:team_id>/transfer', methods=['POST'])
@login_required
def transfer_captain(team_id):
    """Transfer team captain to another member"""
    if current_user.team_id != team_id:
        return jsonify({'success': False, 'message': 'You are not in this team'}), 403
    
    team = Team.query.get_or_404(team_id)
    
    if current_user.id != team.captain_id:
        return jsonify({'success': False, 'message': 'Only captain can transfer ownership'}), 403
    
    new_captain_id = request.form.get('user_id', type=int)
    new_captain = User.query.get(new_captain_id)
    
    if not new_captain or new_captain.team_id != team_id:
        return jsonify({'success': False, 'message': 'User not found in team'}), 404
    
    # Transfer ownership
    team.captain_id = new_captain_id
    current_user.is_team_captain = False
    new_captain.is_team_captain = True
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Transferred captain to {new_captain.username}'
    })


@teams_bp.route('/<int:team_id>/kick/<int:user_id>', methods=['POST'])
@login_required
def kick_member(team_id, user_id):
    """Kick a member from team (captain only)"""
    if current_user.team_id != team_id:
        return jsonify({'success': False, 'message': 'You are not in this team'}), 403
    
    team = Team.query.get_or_404(team_id)
    
    if current_user.id != team.captain_id:
        return jsonify({'success': False, 'message': 'Only captain can kick members'}), 403
    
    if user_id == current_user.id:
        return jsonify({'success': False, 'message': 'Cannot kick yourself'}), 400
    
    user = User.query.get(user_id)
    if not user or user.team_id != team_id:
        return jsonify({'success': False, 'message': 'User not found in team'}), 404
    
    user.team_id = None
    user.is_team_captain = False
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Kicked {user.username} from team'
    })
