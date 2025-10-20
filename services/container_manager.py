"""
Docker Container Orchestration Service
Manages container lifecycle for challenge instances
"""

import docker
import random
import hashlib
import tempfile
import json
from datetime import datetime, timedelta
from pathlib import Path
from flask import current_app
from sqlalchemy.orm import joinedload
from models import db
from models.container import ContainerInstance, ContainerEvent
from models.challenge import Challenge
from models.settings import DockerSettings
from services.cache import cache_service


class ContainerOrchestrator:
    """Orchestrates Docker containers for CTF challenges"""
    
    def __init__(self):
        self.docker_client = None
        self._client_initialized = False
    
    def _ensure_docker_client(self):
        """Ensure Docker client is initialized (lazy initialization)"""
        if self._client_initialized:
            return
        
        try:
            settings = DockerSettings.get_config()
            
            if not settings.hostname:
                # Use local Docker socket
                self.docker_client = docker.from_env()
            elif settings.tls_enabled and settings.ca_cert:
                # Use TLS connection
                tls_config = self._create_tls_config(settings)
                self.docker_client = docker.DockerClient(
                    base_url=settings.hostname,
                    tls=tls_config
                )
            else:
                # Plain TCP connection
                self.docker_client = docker.DockerClient(base_url=settings.hostname)
            
            # Test connection
            self.docker_client.ping()
            if current_app:
                current_app.logger.info("Docker client initialized successfully")
            self._client_initialized = True
            
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Failed to initialize Docker client: {e}")
            self.docker_client = None
            self._client_initialized = False
    
    def _init_docker_client(self):
        """Initialize Docker client with settings (deprecated, use _ensure_docker_client)"""
        self._ensure_docker_client()
    
    def _create_tls_config(self, settings):
        """Create TLS configuration from certificates"""
        try:
            # Write certificates to temp files
            ca_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.pem')
            ca_file.write(settings.ca_cert)
            ca_file.close()
            
            client_cert_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.pem')
            client_cert_file.write(settings.client_cert)
            client_cert_file.close()
            
            client_key_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.pem')
            client_key_file.write(settings.client_key)
            client_key_file.close()
            
            tls_config = docker.tls.TLSConfig(
                client_cert=(client_cert_file.name, client_key_file.name),
                ca_cert=ca_file.name,
                verify=True
            )
            
            return tls_config
        except Exception as e:
            current_app.logger.error(f"Failed to create TLS config: {e}")
            return None
    
    def start_container(self, challenge_id, user_id, ip_address, team_id=None):
        """
        Start a Docker container for a challenge
        
        Args:
            challenge_id: Challenge ID
            user_id: User ID
            ip_address: Client IP address
            team_id: Team ID (optional)
        
        Returns:
            dict: Success/error response with container details
        """
        self._ensure_docker_client()
        
        if not self.docker_client:
            return {
                'success': False,
                'error': 'Docker is not configured. Please contact administrator.'
            }
        
        try:
            # Get challenge and settings
            challenge = Challenge.query.get(challenge_id)
            if not challenge:
                return {'success': False, 'error': 'Challenge not found'}
            
            if not challenge.docker_enabled or not challenge.docker_image:
                return {'success': False, 'error': 'This challenge does not support containers'}
            
            settings = DockerSettings.get_config()
            
            # Check if image is allowed
            if not settings.is_image_allowed(challenge.docker_image):
                return {
                    'success': False,
                    'error': 'This Docker image is not in the allowed repositories'
                }
            
            # Check one container per user limit
            existing_count = ContainerInstance.query.filter_by(
                user_id=user_id
            ).filter(
                ContainerInstance.status.in_(['starting', 'running'])
            ).count()
            
            if existing_count >= settings.max_containers_per_user:
                # Eagerly load the challenge relationship
                existing = ContainerInstance.query.options(
                    db.joinedload(ContainerInstance.challenge)
                ).filter_by(
                    user_id=user_id
                ).filter(
                    ContainerInstance.status.in_(['starting', 'running'])
                ).first()
                
                error_msg = 'You already have a container running. Please stop it before starting a new one.'
                if existing and existing.challenge:
                    error_msg = f'You already have a container running for: {existing.challenge.name}. Please stop it before starting a new one.'
                
                return {
                    'success': False,
                    'error': error_msg,
                    'existing_challenge_id': existing.challenge_id if existing else None
                }
            
            # Check for existing container for this challenge
            existing_container = ContainerInstance.query.filter_by(
                challenge_id=challenge_id,
                user_id=user_id,
                status='running'
            ).first()
            
            if existing_container:
                # Check revert cooldown
                if existing_container.last_revert_time:
                    cooldown_end = existing_container.last_revert_time + timedelta(
                        minutes=settings.revert_cooldown_minutes
                    )
                    if datetime.utcnow() < cooldown_end:
                        remaining = (cooldown_end - datetime.utcnow()).total_seconds()
                        return {
                            'success': False,
                            'error': f'Please wait {int(remaining)} seconds before reverting',
                            'status': 'cooldown',
                            'remaining_seconds': int(remaining)
                        }
                
                return {
                    'success': False,
                    'error': 'Container already running. Use revert to restart.',
                    'status': 'running',
                    'container': existing_container.to_dict()
                }
            
            # Generate session ID
            session_id = hashlib.md5(
                f"{user_id}_{challenge_id}_{datetime.utcnow().timestamp()}".encode()
            ).hexdigest()[:16]
            
            # Create container name
            container_name = f"ctf-challenge-user{user_id}-chal{challenge_id}-{session_id}"
            
            # Get available port
            port = self._get_available_port(settings)
            
            # Create database record with starting status
            instance = ContainerInstance(
                challenge_id=challenge_id,
                user_id=user_id,
                team_id=team_id,
                session_id=session_id,
                container_id=f"starting_{session_id}",  # Temporary, will be updated
                container_name=container_name,
                docker_image=challenge.docker_image,
                port=port,
                host_port=str(port),
                status='starting',
                host_ip=self._get_docker_host(),
                started_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(minutes=settings.container_lifetime_minutes)
            )
            db.session.add(instance)
            db.session.commit()
            
            # Log event
            self._log_event(instance.id, 'starting', 'Starting container', event_type='start')
            
            # Start Docker container
            try:
                container = self.docker_client.containers.run(
                    challenge.docker_image,
                    name=container_name,
                    detach=True,
                    ports={'80/tcp': port},  # Map container port 80 to host port
                    network='ctf_challenges',  # Connect to challenge network
                    environment={
                        'CTF_USER_ID': str(user_id),
                        'CTF_CHALLENGE_ID': str(challenge_id),
                        'CTF_SESSION_ID': session_id
                    },
                    labels={
                        'ctf.challenge_id': str(challenge_id),
                        'ctf.user_id': str(user_id),
                        'ctf.session_id': session_id
                    },
                    restart_policy={'Name': 'no'},
                    remove=False
                )
                
                # Update instance with actual container ID and running status
                instance.container_id = container.id
                instance.status = 'running'
                instance.docker_info = {
                    'short_id': container.short_id,
                    'name': container.name,
                    'image': challenge.docker_image
                }
                
                # Debug logging for expiry time
                current_app.logger.debug(
                    f"Container started: {container.short_id} expires_at={instance.expires_at} "
                    f"expires_at_ms={int(instance.expires_at.timestamp() * 1000)}"
                )
                
                db.session.commit()
                
                # Log success event
                self._log_event(instance.id, 'running', f'Container started on port {port}', event_type='start')
                
                # Set rate limit in Redis
                self._set_rate_limit(user_id, challenge_id)
                
                # Store container session in Redis
                cache_service.set(
                    f"container_session:{session_id}",
                    {
                        'container_id': container.id,
                        'user_id': user_id,
                        'challenge_id': challenge_id,
                        'expires_at': instance.expires_at.isoformat()
                    },
                    ttl=settings.container_lifetime_minutes * 60
                )
                
                # Build connection info
                connection_info = self._build_connection_info(
                    challenge, 
                    instance.host_ip, 
                    port
                )
                
                current_app.logger.info(
                    f"Container started: {container.short_id} for user {user_id} "
                    f"challenge {challenge_id} on port {port}"
                )
                
                return {
                    'success': True,
                    'status': 'running',
                    'container': {
                        **instance.to_dict(),
                        'connection_info': connection_info
                    }
                }
                
            except docker.errors.ImageNotFound:
                # Try to pull the image
                current_app.logger.info(f"Pulling image: {challenge.docker_image}")
                try:
                    self.docker_client.images.pull(challenge.docker_image)
                    # Retry container creation after pull
                    return self.start_container(challenge_id, user_id, ip_address, team_id)
                except Exception as pull_error:
                    instance.status = 'error'
                    instance.error_message = f'Failed to pull image: {str(pull_error)}'
                    db.session.commit()
                    self._log_event(instance.id, 'error', instance.error_message, event_type='error')
                    return {
                        'success': False,
                        'error': f'Docker image not found and pull failed: {str(pull_error)}'
                    }
            
            except Exception as docker_error:
                # Update instance status to error
                instance.status = 'error'
                instance.error_message = str(docker_error)
                db.session.commit()
                
                self._log_event(instance.id, 'error', str(docker_error), event_type='error')
                
                current_app.logger.error(f"Failed to start container: {docker_error}")
                
                return {
                    'success': False,
                    'error': f'Failed to start container: {str(docker_error)}'
                }
        
        except Exception as e:
            current_app.logger.error(f"Container start error: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}'
            }
    
    def stop_container(self, challenge_id, user_id, force=False):
        """Stop a running container"""
        self._ensure_docker_client()
        
        try:
            instance = ContainerInstance.query.filter_by(
                challenge_id=challenge_id,
                user_id=user_id,
                status='running'
            ).first()
            
            if not instance:
                return {'success': False, 'error': 'No running container found'}
            
            # Check cooldown (unless force)
            if not force and instance.last_revert_time:
                settings = DockerSettings.get_config()
                cooldown_end = instance.last_revert_time + timedelta(
                    minutes=settings.revert_cooldown_minutes
                )
                if datetime.utcnow() < cooldown_end:
                    remaining = (cooldown_end - datetime.utcnow()).total_seconds()
                    return {
                        'success': False,
                        'error': f'Please wait {int(remaining)} seconds before stopping',
                        'remaining_seconds': int(remaining)
                    }
            
            # Stop Docker container
            try:
                if self.docker_client:
                    container = self.docker_client.containers.get(instance.container_id)
                    container.stop(timeout=10)
                    container.remove()
                    current_app.logger.info(f"Container stopped: {instance.container_id}")
            except docker.errors.NotFound:
                current_app.logger.warning(f"Container not found in Docker: {instance.container_id}")
            except Exception as e:
                current_app.logger.error(f"Failed to stop Docker container: {e}")
            
            # Update database
            instance.status = 'stopped'
            instance.stopped_at = datetime.utcnow()
            db.session.commit()
            
            # Log event
            self._log_event(instance.id, 'stopped', 'Container stopped by user', event_type='stop')
            
            # Clear Redis cache
            if instance.session_id:
                cache_service.delete(f"container_session:{instance.session_id}")
            
            return {'success': True, 'message': 'Container stopped successfully'}
        
        except Exception as e:
            current_app.logger.error(f"Stop container error: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    def revert_container(self, challenge_id, user_id, ip_address, team_id=None):
        """Revert (restart) a container"""
        self._ensure_docker_client()
        
        try:
            # Stop existing container
            stop_result = self.stop_container(challenge_id, user_id, force=True)
            
            if not stop_result['success']:
                return stop_result
            
            # Update last revert time
            instance = ContainerInstance.query.filter_by(
                challenge_id=challenge_id,
                user_id=user_id
            ).order_by(ContainerInstance.started_at.desc()).first()
            
            if instance:
                instance.last_revert_time = datetime.utcnow()
                db.session.commit()
            
            # Start new container
            return self.start_container(challenge_id, user_id, ip_address, team_id)
        
        except Exception as e:
            current_app.logger.error(f"Revert container error: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    def get_container_status(self, challenge_id, user_id):
        """Get status of user's container for a challenge"""
        self._ensure_docker_client()
        
        instance = ContainerInstance.query.filter_by(
            challenge_id=challenge_id,
            user_id=user_id
        ).filter(
            ContainerInstance.status.in_(['starting', 'running'])
        ).first()
        
        if not instance:
            return {'success': True, 'status': 'none', 'container': None}
        
        # DON'T check expiry here - let the reconciliation task handle cleanup
        # This prevents timezone issues between server/client
        # The client-side countdown will show expiry status
        
        # Debug logging
        current_app.logger.debug(
            f"Container status: {instance.container_name} expires_at_ms={instance.to_dict().get('expires_at_ms')}"
        )
        
        # Build connection info
        challenge = Challenge.query.get(challenge_id)
        connection_info = self._build_connection_info(
            challenge,
            instance.host_ip,
            instance.host_port
        )
        
        return {
            'success': True,
            'status': instance.status,
            'container': {
                **instance.to_dict(),
                'connection_info': connection_info
            }
        }
    
    def cleanup_expired_containers(self):
        """Clean up expired containers (called by scheduler)"""
        self._ensure_docker_client()
        
        try:
            expired = ContainerInstance.query.filter(
                ContainerInstance.status == 'running',
                ContainerInstance.expires_at < datetime.utcnow()
            ).all()
            
            for instance in expired:
                try:
                    if self.docker_client:
                        container = self.docker_client.containers.get(instance.container_id)
                        container.stop(timeout=10)
                        container.remove()
                except:
                    pass
                
                instance.status = 'stopped'
                instance.stopped_at = datetime.utcnow()
                self._log_event(instance.id, 'expired', 'Container expired and cleaned up', event_type='expire')
            
            db.session.commit()
            current_app.logger.info(f"Cleaned up {len(expired)} expired containers")
            
        except Exception as e:
            current_app.logger.error(f"Cleanup error: {e}", exc_info=True)
    
    def _get_docker_host(self):
        """Get Docker host IP"""
        settings = DockerSettings.get_config()
        
        if settings.hostname:
            # Extract hostname from tcp://host:port
            host = settings.hostname.replace('tcp://', '').replace('https://', '').split(':')[0]
            return host
        
        # Use local hostname
        import socket
        return socket.gethostname()
    
    def _get_available_port(self, settings):
        """Get an available port in the configured range"""
        # Get ports in use
        used_ports = set()
        instances = ContainerInstance.query.filter_by(status='running').all()
        for instance in instances:
            if instance.host_port:
                used_ports.add(instance.host_port)
        
        # Find available port
        max_attempts = 100
        for _ in range(max_attempts):
            port = random.randint(settings.port_range_start, settings.port_range_end)
            if port not in used_ports:
                return port
        
        raise Exception("No available ports in range")
    
    def _build_connection_info(self, challenge, host_ip, port):
        """Build connection info string with replacements"""
        if not challenge.docker_connection_info:
            return f"http://{host_ip}:{port}"
        
        # Replace placeholders
        info = challenge.docker_connection_info
        info = info.replace('{host}', host_ip)
        info = info.replace('{port}', str(port))
        
        return info
    
    def _set_rate_limit(self, user_id, challenge_id):
        """Set rate limit for container starts"""
        key = f"container_rate_limit:{user_id}:{challenge_id}"
        cache_service.set(key, 1, ttl=300)  # 5 minute cooldown
    
    def _log_event(self, instance_id, status, message, event_type='lifecycle', challenge_id=None, user_id=None, ip_address=None, container_id=None):
        """Log container event"""
        try:
            # Get instance to extract challenge_id and user_id if not provided
            if not challenge_id or not user_id:
                instance = ContainerInstance.query.get(instance_id)
                if instance:
                    challenge_id = challenge_id or instance.challenge_id
                    user_id = user_id or instance.user_id
                    container_id = container_id or instance.container_id
            
            event = ContainerEvent(
                container_instance_id=instance_id,
                challenge_id=challenge_id,
                user_id=user_id,
                event_type=event_type,
                status=status,
                message=message,
                ip_address=ip_address,
                container_id=container_id,
                timestamp=datetime.utcnow()
            )
            db.session.add(event)
            db.session.commit()
        except Exception as e:
            current_app.logger.error(f"Failed to log container event: {e}")
            # Don't let logging errors break the main flow
            db.session.rollback()
    
    def list_available_images(self):
        """List available Docker images"""
        self._ensure_docker_client()
        
        if not self.docker_client:
            return {'success': False, 'error': 'Docker not configured'}
        
        try:
            settings = DockerSettings.get_config()
            images = self.docker_client.images.list()
            
            allowed_repos = settings.get_allowed_repositories_list()
            
            result = []
            for image in images:
                for tag in image.tags:
                    # Check if allowed
                    if allowed_repos and not any(tag.startswith(repo) for repo in allowed_repos):
                        continue
                    
                    result.append({
                        'tag': tag,
                        'id': image.short_id,
                        'size': image.attrs.get('Size', 0),
                        'created': image.attrs.get('Created', '')
                    })
            
            return {'success': True, 'images': result}
        
        except Exception as e:
            current_app.logger.error(f"Failed to list images: {e}")
            return {'success': False, 'error': str(e)}


# Global instance
container_orchestrator = ContainerOrchestrator()
