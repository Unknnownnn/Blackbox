#!/bin/bash
# Get the Docker socket group ID from the host
# This script exports DOCKER_GID for use with docker-compose

if [ -e /var/run/docker.sock ]; then
    DOCKER_GID=$(stat -c '%g' /var/run/docker.sock 2>/dev/null)
    if [ -n "$DOCKER_GID" ]; then
        echo "export DOCKER_GID=$DOCKER_GID"
    else
        echo "export DOCKER_GID=999"
    fi
else
    echo "Warning: Docker socket not found, using default GID 999" >&2
    echo "export DOCKER_GID=999"
fi
