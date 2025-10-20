"""
Container Management Routes
Endpoints for starting, stopping, and managing challenge containers
"""

from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from models import db
from models.container import ContainerInstance, ContainerEvent
from models.challenge import Challenge
from models.settings import DockerSettings
from services.container_manager import container_orchestrator
from datetime import datetime

container_bp = Blueprint('container', __name__, url_prefix='/container')


def get_client_ip():
    """Get client IP address from request"""
    if request.environ.get('HTTP_X_FORWARDED_FOR'):
        return request.environ['HTTP_X_FORWARDED_FOR'].split(',')[0]
    return request.environ.get('REMOTE_ADDR', '0.0.0.0')


@container_bp.route('/start', methods=['POST'])
@login_required
def start_container():
    """Start a Docker container for a challenge"""
    try:
        data = request.get_json()
        challenge_id = data.get('challenge_id')
        
        if not challenge_id:
            return jsonify({'success': False, 'error': 'Missing challenge_id'}), 400
        
        # Get user's team (if any)
        team = current_user.get_team()
        team_id = team.id if team else None
        
        # Start container
        result = container_orchestrator.start_container(
            challenge_id=challenge_id,
            user_id=current_user.id,
            ip_address=get_client_ip(),
            team_id=team_id
        )
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500


@container_bp.route('/stop', methods=['POST'])
@login_required
def stop_container():
    """Stop a running container"""
    try:
        data = request.get_json()
        challenge_id = data.get('challenge_id')
        
        if not challenge_id:
            return jsonify({'success': False, 'error': 'Missing challenge_id'}), 400
        
        result = container_orchestrator.stop_container(
            challenge_id=challenge_id,
            user_id=current_user.id
        )
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500


@container_bp.route('/revert', methods=['POST'])
@login_required
def revert_container():
    """Revert (restart) a container"""
    try:
        data = request.get_json()
        challenge_id = data.get('challenge_id')
        
        if not challenge_id:
            return jsonify({'success': False, 'error': 'Missing challenge_id'}), 400
        
        # Get user's team (if any)
        team = current_user.get_team()
        team_id = team.id if team else None
        
        result = container_orchestrator.revert_container(
            challenge_id=challenge_id,
            user_id=current_user.id,
            ip_address=get_client_ip(),
            team_id=team_id
        )
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500


@container_bp.route('/status', methods=['GET'])
@login_required
def get_status():
    """Get status of user's container for a challenge"""
    try:
        challenge_id = request.args.get('challenge_id', type=int)
        
        if not challenge_id:
            return jsonify({'success': False, 'error': 'Missing challenge_id'}), 400
        
        result = container_orchestrator.get_container_status(
            challenge_id=challenge_id,
            user_id=current_user.id
        )
        
        return jsonify(result), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500


@container_bp.route('/my-containers', methods=['GET'])
@login_required
def list_my_containers():
    """List all containers for current user"""
    try:
        containers = ContainerInstance.query.filter_by(
            user_id=current_user.id
        ).filter(
            ContainerInstance.status.in_(['starting', 'running'])
        ).all()
        
        result = []
        for container in containers:
            challenge = Challenge.query.get(container.challenge_id)
            connection_info = container_orchestrator._build_connection_info(
                challenge,
                container.host_ip,
                container.host_port
            ) if challenge and challenge.docker_connection_info else None
            
            result.append({
                **container.to_dict(),
                'challenge_name': challenge.name if challenge else 'Unknown',
                'connection_info': connection_info
            })
        
        return jsonify({
            'success': True,
            'containers': result
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500


@container_bp.route('/force-cleanup', methods=['POST'])
@login_required
def force_cleanup():
    """
    Force cleanup of user's expired/stuck containers.
    Removes DB records and attempts to stop/remove Docker containers.
    """
    try:
        data = request.get_json() or {}
        challenge_id = data.get('challenge_id')
        
        # Find containers to clean up
        query = ContainerInstance.query.filter_by(user_id=current_user.id)
        
        if challenge_id:
            query = query.filter_by(challenge_id=challenge_id)
        else:
            # Clean up expired/stopped containers only
            query = query.filter(
                db.or_(
                    ContainerInstance.status.in_(['stopped', 'error']),
                    ContainerInstance.expires_at < datetime.utcnow()
                )
            )
        
        containers = query.all()
        
        if not containers:
            return jsonify({
                'success': False,
                'error': 'No containers found to clean up'
            }), 404
        
        cleaned_count = 0
        errors = []
        
        # Ensure Docker client is available
        container_orchestrator._ensure_docker_client()
        
        for container in containers:
            try:
                # Try to stop/remove from Docker if exists
                if container_orchestrator.docker_client:
                    try:
                        docker_container = container_orchestrator.docker_client.containers.get(container.container_id)
                        if docker_container.status == 'running':
                            docker_container.stop(timeout=5)
                        docker_container.remove(force=True)
                    except Exception as docker_err:
                        # Container might already be gone, that's okay
                        pass
                
                # Remove from database
                db.session.delete(container)
                cleaned_count += 1
                
            except Exception as e:
                errors.append(f"Container {container.id}: {str(e)}")
        
        db.session.commit()
        
        if cleaned_count > 0:
            return jsonify({
                'success': True,
                'message': f'Cleaned up {cleaned_count} container(s)',
                'cleaned_count': cleaned_count,
                'errors': errors if errors else None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to clean up containers',
                'errors': errors
            }), 500
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500
