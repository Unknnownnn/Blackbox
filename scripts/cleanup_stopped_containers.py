#!/usr/bin/env python3
"""
Cleanup script for stopped CTF container instances.

This script removes Docker containers and database records for containers
that are marked as 'stopped' in the database. It only affects containers
created by this CTF platform (those starting with 'ctf-challenge-').

Usage:
    python scripts/cleanup_stopped_containers.py

Requirements:
    - Docker daemon running
    - Database connection available
    - Run from project root directory
"""

import os
import sys
import logging
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models.container import ContainerInstance
from services.container_manager import ContainerManager
from services.container_manager import ContainerOrchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def cleanup_stopped_containers():
    """Clean up all stopped container instances created by this CTF platform."""

    app = create_app()
    cleaned_count = 0
    error_count = 0

    with app.app_context():
        try:
            # Get all stopped container instances
            stopped_instances = ContainerInstance.query.filter_by(status='stopped').all()

            if not stopped_instances:
                logger.info("No stopped containers found to clean up")
                return 0, 0

            logger.info(f"Found {len(stopped_instances)} stopped container instances")

            for instance in stopped_instances:
                try:
                    container_name = instance.container_name

                    # Only clean up containers created by this CTF platform
                    if not container_name.startswith('ctf-challenge-'):
                        logger.debug(f"Skipping non-CTF container: {container_name}")
                        continue

                    logger.info(f"Processing stopped container: {container_name} (ID: {instance.id})")

                    # Check if Docker container exists and remove it
                    try:
                        orchestrator = ContainerOrchestrator()
                        docker_client = orchestrator._ensure_docker_client()
                        docker_container = docker_client.containers.get(container_name)

                        # Check container status
                        docker_container.reload()
                        container_status = docker_container.status

                        if container_status in ['running', 'restarting', 'paused']:
                            logger.warning(f"Container {container_name} is {container_status}, skipping removal")
                            continue

                        # Remove the Docker container
                        logger.info(f"Removing Docker container: {container_name}")
                        docker_container.remove(force=True)

                    except Exception as e:
                        if "404" in str(e) or "No such container" in str(e):
                            logger.debug(f"Docker container {container_name} already removed or doesn't exist")
                        else:
                            logger.error(f"Error removing Docker container {container_name}: {e}")
                            error_count += 1
                            continue

                    # Remove database record
                    logger.info(f"Removing database record for container {container_name}")
                    ContainerInstance.query.filter_by(id=instance.id).delete()
                    cleaned_count += 1

                except Exception as e:
                    logger.error(f"Error processing container {instance.container_name}: {e}")
                    error_count += 1
                    continue

            # Commit all database changes
            from app import db
            db.session.commit()

        except Exception as e:
            logger.error(f"Database error during cleanup: {e}")
            from app import db
            db.session.rollback()
            error_count += 1

    logger.info(f"Cleanup completed: {cleaned_count} containers cleaned, {error_count} errors")
    return cleaned_count, error_count


def cleanup_expired_containers():
    """Clean up containers that have expired but are still marked as running."""

    app = create_app()
    cleaned_count = 0
    error_count = 0

    with app.app_context():
        try:
            # Get containers that are marked as running but have expired
            expired_instances = ContainerInstance.query.filter(
                ContainerInstance.status.in_(['running', 'starting']),
                ContainerInstance.expires_at < datetime.utcnow()
            ).all()

            if not expired_instances:
                logger.info("No expired containers found to clean up")
                return 0, 0

            logger.info(f"Found {len(expired_instances)} expired container instances")

            for instance in expired_instances:
                try:
                    container_name = instance.container_name
                    logger.info(f"Processing expired container: {container_name} (ID: {instance.id})")

                    # Stop the container if it's running
                    try:
                        container_manager = ContainerManager()
                        container_manager.stop_container(instance.challenge_id, instance.user_id, force=True)
                        logger.info(f"Stopped expired container: {container_name}")
                    except Exception as e:
                        logger.error(f"Error stopping expired container {container_name}: {e}")

                    # Mark as stopped in database
                    instance.status = 'stopped'
                    cleaned_count += 1

                except Exception as e:
                    logger.error(f"Error processing expired container {instance.container_name}: {e}")
                    error_count += 1
                    continue

            # Commit database changes
            from app import db
            db.session.commit()

        except Exception as e:
            logger.error(f"Database error during expired cleanup: {e}")
            from app import db
            db.session.rollback()
            error_count += 1

    logger.info(f"Expired cleanup completed: {cleaned_count} containers cleaned, {error_count} errors")
    return cleaned_count, error_count


def main():
    """Main entry point for the cleanup script."""

    logger.info("Starting CTF container cleanup...")

    # Clean up stopped containers
    stopped_cleaned, stopped_errors = cleanup_stopped_containers()

    # Clean up expired containers
    expired_cleaned, expired_errors = cleanup_expired_containers()

    total_cleaned = stopped_cleaned + expired_cleaned
    total_errors = stopped_errors + expired_errors

    logger.info("=" * 50)
    logger.info("CLEANUP SUMMARY")
    logger.info("=" * 50)
    logger.info(f"Stopped containers cleaned: {stopped_cleaned}")
    logger.info(f"Expired containers cleaned: {expired_cleaned}")
    logger.info(f"Total containers cleaned: {total_cleaned}")
    logger.info(f"Total errors: {total_errors}")
    logger.info("=" * 50)

    if total_errors > 0:
        logger.warning(f"Completed with {total_errors} errors. Check logs above for details.")
        sys.exit(1)
    else:
        logger.info("Cleanup completed successfully!")
        sys.exit(0)


if __name__ == '__main__':
    main()