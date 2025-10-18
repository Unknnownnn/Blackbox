# Hints Routes - Add this to routes/__init__.py or create routes/hints.py

from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from models import db
from models.hint import Hint, HintUnlock
from models.challenge import Challenge
from models.user import User
from models.team import Team

hints_bp = Blueprint('hints', __name__, url_prefix='/hints')


@hints_bp.route('/challenge/<int:challenge_id>', methods=['GET'])
@login_required
def get_challenge_hints(challenge_id):
    """Get hints for a challenge"""
    challenge = Challenge.query.get_or_404(challenge_id)
    
    if not challenge.is_visible and not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Challenge not found'}), 404
    
    hints = Hint.query.filter_by(challenge_id=challenge_id).order_by(Hint.order).all()
    team = current_user.get_team()
    
    hints_data = []
    for hint in hints:
        # Check if unlocked
        if team:
            unlocked = hint.is_unlocked_by_team(team.id)
            can_unlock, reason = hint.can_unlock(team_id=team.id)
        else:
            unlocked = hint.is_unlocked_by_user(current_user.id)
            can_unlock, reason = hint.can_unlock(user_id=current_user.id)
        
        hint_data = {
            'id': hint.id,
            'cost': hint.cost,
            'order': hint.order,
            'unlocked': unlocked,
            'can_unlock': can_unlock or unlocked,  # If already unlocked, consider it "can unlock"
            'requires_hint_id': hint.requires_hint_id,
        }
        
        if not can_unlock and not unlocked:
            hint_data['locked_reason'] = reason
        
        if unlocked or current_user.is_admin:
            hint_data['content'] = hint.content
        
        hints_data.append(hint_data)
    
    return jsonify({'success': True, 'hints': hints_data})


@hints_bp.route('/<int:hint_id>/unlock', methods=['POST'])
@login_required
def unlock_hint(hint_id):
    """Unlock a hint by paying the cost"""
    hint = Hint.query.get_or_404(hint_id)
    challenge = hint.challenge
    
    if not challenge.is_visible and not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Challenge not found'}), 404
    
    team = current_user.get_team()
    team_id = team.id if team else None
    
    # Check if already unlocked
    if team:
        already_unlocked = hint.is_unlocked_by_team(team_id)
    else:
        already_unlocked = hint.is_unlocked_by_user(current_user.id)
    
    if already_unlocked:
        return jsonify({'success': False, 'message': 'Hint already unlocked'}), 400
    
    # Check if prerequisites are met
    can_unlock, reason = hint.can_unlock(user_id=current_user.id, team_id=team_id)
    if not can_unlock:
        return jsonify({'success': False, 'message': reason}), 400
    
    # Get current score
    if team:
        current_score = team.get_score()
    else:
        current_score = current_user.get_score()
    
    # Calculate new score (can go negative)
    new_score = current_score - hint.cost
    
    # Create hint unlock record
    try:
        hint_unlock = HintUnlock(
            hint_id=hint.id,
            user_id=current_user.id,
            team_id=team_id,
            cost_paid=hint.cost
        )
        db.session.add(hint_unlock)
        
        # Log hint unlock for tracking
        import logging
        logger = logging.getLogger('blackbox')
        
        if team:
            logger.info(f"HINT_UNLOCK: User '{current_user.username}' (ID: {current_user.id}) "
                       f"from Team '{team.name}' (ID: {team.id}) unlocked hint #{hint.order} "
                       f"for Challenge '{challenge.name}' (ID: {challenge.id}). "
                       f"Cost: {hint.cost} points. New score: {new_score}")
        else:
            logger.info(f"HINT_UNLOCK: User '{current_user.username}' (ID: {current_user.id}) "
                       f"unlocked hint #{hint.order} for Challenge '{challenge.name}' (ID: {challenge.id}). "
                       f"Cost: {hint.cost} points. New score: {new_score}")
        

        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Hint unlocked for {hint.cost} points',
            'content': hint.content,
            'new_score': new_score
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


# Admin routes for managing hints
@hints_bp.route('/admin/challenge/<int:challenge_id>/hints', methods=['GET'])
@login_required
def admin_list_hints(challenge_id):
    """List all hints for a challenge (admin only)"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Admin access required'}), 403
    
    challenge = Challenge.query.get_or_404(challenge_id)
    hints = Hint.query.filter_by(challenge_id=challenge_id).order_by(Hint.order).all()
    
    hints_data = [{'id': h.id, 'content': h.content, 'cost': h.cost, 'order': h.order} for h in hints]
    
    return jsonify({'success': True, 'hints': hints_data})


@hints_bp.route('/admin/challenge/<int:challenge_id>/hints', methods=['POST'])
@login_required
def admin_create_hint(challenge_id):
    """Create a new hint (admin only)"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Admin access required'}), 403
    
    challenge = Challenge.query.get_or_404(challenge_id)
    
    content = request.form.get('content', '').strip()
    cost = request.form.get('cost', 0, type=int)
    order = request.form.get('order', 0, type=int)
    
    if not content:
        return jsonify({'success': False, 'message': 'Hint content is required'}), 400
    
    try:
        hint = Hint(
            challenge_id=challenge_id,
            content=content,
            cost=cost,
            order=order
        )
        db.session.add(hint)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Hint created successfully',
            'hint': hint.to_dict(include_content=True)
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@hints_bp.route('/admin/hints/<int:hint_id>', methods=['PUT', 'DELETE'])
@login_required
def admin_manage_hint(hint_id):
    """Update or delete a hint (admin only)"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Admin access required'}), 403
    
    hint = Hint.query.get_or_404(hint_id)
    
    if request.method == 'DELETE':
        try:
            db.session.delete(hint)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Hint deleted successfully'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500
    
    # UPDATE
    content = request.form.get('content')
    cost = request.form.get('cost', type=int)
    order = request.form.get('order', type=int)
    
    try:
        if content:
            hint.content = content
        if cost is not None:
            hint.cost = cost
        if order is not None:
            hint.order = order
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Hint updated successfully',
            'hint': hint.to_dict(include_content=True)
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
