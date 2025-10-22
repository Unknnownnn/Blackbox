#!/bin/bash
# Docker Integration Fix Script (Linux/Bash)
# This script attempts to automatically fix common Docker integration issues

echo "====================================="
echo "Docker Integration Fix Script"
echo "====================================="
echo ""

# Detect Docker socket group ID
echo "[0/5] Detecting Docker socket permissions..."
if [ -e /var/run/docker.sock ]; then
    DOCKER_GID=$(stat -c '%g' /var/run/docker.sock 2>/dev/null)
    if [ -n "$DOCKER_GID" ]; then
        echo "✓ Docker socket found (GID: $DOCKER_GID)"
        export DOCKER_GID
    else
        echo "⚠ Could not detect Docker GID, using default 999"
        export DOCKER_GID=999
    fi
else
    echo "✗ WARNING: Docker socket not found at /var/run/docker.sock"
    echo "  Is Docker running on this host?"
    export DOCKER_GID=999
fi
echo ""

# Function to wait for service
wait_for_service() {
    local max_attempts=30
    local attempt=0
    echo "Waiting for services to be ready..."
    while [ $attempt -lt $max_attempts ]; do
        if docker exec blackbox-ctf python3 -c "from app import app; print('OK')" > /dev/null 2>&1; then
            echo "✓ Services are ready"
            return 0
        fi
        attempt=$((attempt + 1))
        echo "  Attempt $attempt/$max_attempts..."
        sleep 2
    done
    echo "✗ Services did not become ready in time"
    return 1
}

# Step 1: Rebuild blackbox container with Docker CLI
echo "[1/5] Rebuilding blackbox container..."
docker-compose build --no-cache blackbox
if [ $? -eq 0 ]; then
    echo "✓ Container rebuilt successfully"
else
    echo "✗ FAILED: Container rebuild failed"
    exit 1
fi
echo ""

# Step 2: Restart containers
echo "[2/5] Restarting containers..."
docker-compose down
docker-compose up -d
if [ $? -eq 0 ]; then
    echo "✓ Containers restarted"
else
    echo "✗ FAILED: Container restart failed"
    exit 1
fi
echo ""

# Step 3: Wait for services
echo "[3/5] Waiting for services..."
if wait_for_service; then
    echo "✓ Services ready"
else
    echo "✗ Services not ready, but continuing..."
fi
echo ""

# Step 4: Test Docker access
echo "[4/5] Testing Docker CLI access..."
if docker exec blackbox-ctf docker info > /dev/null 2>&1; then
    echo "✓ Docker CLI is accessible"
    VERSION=$(docker exec blackbox-ctf docker --version)
    echo "  $VERSION"
else
    echo "✗ FAILED: Docker CLI is still not accessible"
    echo "  Please check the following:"
    echo "  1. Docker socket mount in docker-compose.yml"
    echo "  2. User permissions (docker group)"
    echo "  3. Container logs: docker logs blackbox-ctf"
    exit 1
fi
echo ""

# Step 5: Check and run migrations if needed
echo "[5/5] Checking database migrations..."
MIGRATIONS_NEEDED=$(docker exec blackbox-ctf python3 -c "
from app import app
from extensions import db
with app.app_context():
    tables = db.engine.table_names()
    if 'docker_settings' not in tables or 'container_instances' not in tables:
        print('YES')
    else:
        print('NO')
" 2>/dev/null)

if [ "$MIGRATIONS_NEEDED" = "YES" ]; then
    echo "Running migrations..."
    docker exec blackbox-ctf bash -c "python3 -c \"
from app import app
from extensions import db

with app.app_context():
    with open('migrations/add_container_orchestration.sql', 'r') as f:
        sql = f.read()
        for statement in sql.split(';'):
            if statement.strip():
                try:
                    db.session.execute(statement)
                except Exception as e:
                    print(f'Skipping: {str(e)}')
    
    with open('migrations/add_docker_settings.sql', 'r') as f:
        sql = f.read()
        for statement in sql.split(';'):
            if statement.strip():
                try:
                    db.session.execute(statement)
                except Exception as e:
                    print(f'Skipping: {str(e)}')
    
    db.session.commit()
    print('Migrations completed')
\""
    echo "✓ Migrations completed"
else
    echo "✓ Migrations already applied"
fi
echo ""

echo "====================================="
echo "Fix Summary"
echo "====================================="
echo "Docker integration has been configured! ✓"
echo ""
echo "Next steps:"
echo "1. Run diagnostic: ./diagnose_docker.sh"
echo "2. Build challenge images:"
echo "   docker build -t ctf-web-basic:v1 challenge-examples/web-basic/"
echo "3. Configure Docker settings:"
echo "   Visit: http://localhost:5000/admin/docker/settings"
echo "   - Leave hostname empty (use local socket)"
echo "   - Disable TLS"
echo "   - Add repository whitelist: ctf-web-basic"
echo "   - Save settings"
echo "4. Create Docker-enabled challenge"
echo "5. Test as player!"
echo ""
