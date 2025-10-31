#!/bin/bash
# Fix crashing issues and deploy stable configuration

echo "=== BlackBox CTF Crash Fix Deployment ==="
echo "This fixes worker crashes under high load (200+ users)"
echo ""

echo "Changes being applied:"
echo "1. Switch from eventlet to gevent (more stable)"
echo "2. Add worker crash detection and auto-restart"
echo "3. More aggressive worker recycling (5000 requests)"
echo "4. Better health checks"
echo ""

# Check if containers are running
if docker-compose ps | grep -q "blackbox-ctf"; then
    echo "Backing up logs before restart..."
    docker-compose logs --tail=500 blackbox > crash_logs_$(date +%Y%m%d_%H%M%S).log
fi

# Stop everything cleanly
echo "Stopping containers..."
docker-compose down

# Clean up any stale containers
echo "Cleaning up..."
docker-compose rm -f

# Rebuild with new dependencies (gevent)
echo "Rebuilding with gevent worker (this may take a few minutes)..."
docker-compose build --no-cache blackbox

# Start services
echo "Starting services..."
docker-compose up -d

# Wait for startup
echo "Waiting for services to start..."
sleep 15

# Check status
echo ""
echo "=== Service Status ==="
docker-compose ps

echo ""
echo "=== Worker Status ==="
docker-compose exec blackbox ps aux | grep gunicorn || echo "Workers starting..."

echo ""
echo "=== Health Check ==="
sleep 5
curl -f http://localhost:8000/health 2>/dev/null && echo "✓ App is healthy" || echo "✗ App health check failed"

echo ""
echo "=== Configuration Summary ==="
echo "Worker class: gevent (changed from eventlet)"
echo "Workers: 8"
echo "Worker connections: 2000 per worker"
echo "Max requests per worker: 5000 (auto-restart after)"
echo "Timeout: 300 seconds"
echo "Auto-restart: enabled"
echo ""

echo "=== Monitoring Commands ==="
echo "Watch logs: docker-compose logs -f blackbox"
echo "Check workers: docker-compose exec blackbox ps aux | grep gunicorn"
echo "Resource usage: docker stats"
echo "Database connections: docker-compose exec db mysql -ublackbox_user -pblackbox_password -e \"SHOW STATUS LIKE 'Threads_connected';\""
echo ""

echo "=== Why This Fixes Crashes ==="
echo "1. Gevent handles database I/O better than eventlet"
echo "2. Workers restart every 5000 requests (prevents memory leaks)"
echo "3. Faster health checks detect and restart frozen workers"
echo "4. Auto-restart policy recovers from crashes automatically"
echo ""

# Show recent logs
echo "=== Recent Logs ==="
docker-compose logs --tail=30 blackbox

echo ""
echo "✓ Deployment complete. Monitor for 10 minutes to verify stability."
