"""
Container Reconciliation Background Task
Periodically syncs database container_instances status with actual Docker container state.
Handles:
- Containers marked 'stopped' in DB but still running in Docker -> stop them
- Containers marked 'running'/'starting' in DB but missing in Docker -> mark as 'stopped'
- Expired containers that should be cleaned up
"""

import logging
import time
from datetime import datetime
from sqlalchemy.orm import joinedload
from models import db
from models.container import ContainerInstance, ContainerEvent
from services.container_manager import container_orchestrator

logger = logging.getLogger(__name__)


def reconcile_containers(app):
    """
    Reconcile DB container instances with actual Docker containers.
    Run this in a background thread/scheduler.
    """
    with app.app_context():
        try:
            # Get Docker client
            container_orchestrator._ensure_docker_client()
            if not container_orchestrator.docker_client:
                logger.warning("Docker client not available for reconciliation")
                return
            
            # Get all active containers from database
            db_containers = ContainerInstance.query.filter(
                ContainerInstance.status.in_(['starting', 'running', 'stopping'])
            ).all()
            
            # Get all running containers from Docker
            docker_containers = {}
            try:
                all_docker_containers = container_orchestrator.docker_client.containers.list(
                    all=True, 
                    filters={'name': 'ctf-challenge'}
                )
                for dc in all_docker_containers:
                    docker_containers[dc.id] = dc
            except Exception as e:
                logger.error(f"Failed to list Docker containers: {e}")
                return
            
            reconciled_count = 0
            stopped_count = 0
            marked_stopped_count = 0
            
            for db_container in db_containers:
                try:
                    # Check if container exists in Docker
                    docker_container = docker_containers.get(db_container.container_id)
                    
                    if not docker_container:
                        # Container missing in Docker but marked active in DB
                        if db_container.status in ['starting', 'running']:
                            logger.info(f"Container {db_container.container_name} missing in Docker, marking as stopped")
                            db_container.status = 'stopped'
                            db_container.error_message = 'Container not found in Docker'
                            marked_stopped_count += 1
                        continue
                    
                    # Container exists - check consistency
                    docker_status = docker_container.status  # 'running', 'exited', 'created', etc.
                    
                    # If DB says stopped but Docker is running, stop it
                    if db_container.status == 'stopped' and docker_status == 'running':
                        logger.info(f"Stopping Docker container {db_container.container_name} (marked stopped in DB)")
                        try:
                            docker_container.stop(timeout=10)
                            docker_container.remove(force=True)
                            stopped_count += 1
                        except Exception as e:
                            logger.error(f"Failed to stop container {db_container.container_name}: {e}")
                    
                    # If Docker is exited but DB says running, update DB
                    elif db_container.status in ['starting', 'running'] and docker_status in ['exited', 'dead']:
                        logger.info(f"Container {db_container.container_name} has exited, marking as stopped")
                        db_container.status = 'stopped'
                        db_container.error_message = f'Container exited with status: {docker_status}'
                        marked_stopped_count += 1
                    
                    # Check if expired
                    if db_container.expires_at and datetime.utcnow() > db_container.expires_at:
                        if db_container.status in ['starting', 'running']:
                            logger.info(f"Container {db_container.container_name} has expired, stopping")
                            try:
                                if docker_status == 'running':
                                    docker_container.stop(timeout=10)
                                docker_container.remove(force=True)
                                stopped_count += 1
                            except Exception as e:
                                logger.error(f"Failed to stop expired container: {e}")
                            
                            db_container.status = 'stopped'
                            db_container.error_message = 'Container expired'
                            marked_stopped_count += 1
                    
                    reconciled_count += 1
                    
                except Exception as e:
                    logger.error(f"Error reconciling container {db_container.id}: {e}")
                    continue
            
            # Commit all changes
            db.session.commit()
            
            if reconciled_count > 0 or stopped_count > 0 or marked_stopped_count > 0:
                logger.info(
                    f"Reconciliation complete: {reconciled_count} checked, "
                    f"{stopped_count} stopped in Docker, {marked_stopped_count} marked stopped in DB"
                )
        
        except Exception as e:
            logger.error(f"Container reconciliation failed: {e}")
            db.session.rollback()


def run_reconciliation_loop(app, interval_seconds=60):
    """
    Run reconciliation in a loop (for background thread).
    
    Args:
        app: Flask app instance
        interval_seconds: Seconds between reconciliation runs (default: 60)
    """
    logger.info(f"Starting container reconciliation loop (interval: {interval_seconds}s)")
    
    while True:
        try:
            reconcile_containers(app)
        except Exception as e:
            logger.error(f"Reconciliation loop error: {e}")
        
        time.sleep(interval_seconds)
