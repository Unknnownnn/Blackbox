#!/bin/bash
# Emergency fix script when site goes down
# Run this when you see 504 errors

echo "=== EMERGENCY SITE RECOVERY ==="
echo "Time: $(date)"
echo ""

# Step 1: Check what's wrong
echo "Step 1: Diagnosing issue..."
echo ""

echo "Container Status:"
docker-compose ps
echo ""

# Step 2: Check if database is responding
echo "Step 2: Testing database..."
if docker-compose exec -T db mysql -ublackbox_user -pblackbox_password -e "SELECT 1;" > /dev/null 2>&1; then
    echo "✓ Database is responding"
    
    # Check connection count
    CONN=$(docker-compose exec -T db mysql -ublackbox_user -pblackbox_password -e "SHOW STATUS LIKE 'Threads_connected';" 2>&1 | awk 'NR==2 {print $2}')
    echo "  Current connections: $CONN"
    
    if [ "$CONN" -gt 450 ]; then
        echo "  ⚠ CRITICAL: Near max connections!"
        echo ""
        echo "Action: Restarting app to clear connections..."
        docker-compose restart blackbox
        echo "Waiting for app to restart..."
        sleep 10
        echo "✓ App restarted"
    fi
else
    echo "✗ Database NOT responding"
    echo ""
    echo "Action: Restarting database..."
    docker-compose restart db
    echo "Waiting for database to restart..."
    sleep 15
    echo "✓ Database restarted"
fi
echo ""

# Step 3: Check if app is responding
echo "Step 3: Testing Flask app..."
if docker-compose exec -T blackbox curl -f --max-time 5 http://localhost:8000/health > /dev/null 2>&1; then
    echo "✓ Flask app is responding"
else
    echo "✗ Flask app NOT responding"
    echo ""
    echo "Action: Checking worker status..."
    docker-compose exec blackbox ps aux | grep gunicorn | head -10
    echo ""
    echo "Action: Restarting app..."
    docker-compose restart blackbox
    echo "Waiting for app to restart..."
    sleep 10
    echo "✓ App restarted"
fi
echo ""

# Step 4: Check nginx
echo "Step 4: Testing nginx..."
if docker-compose exec -T nginx nginx -t > /dev/null 2>&1; then
    echo "✓ Nginx config is valid"
else
    echo "✗ Nginx config has errors"
    docker-compose exec nginx nginx -t
fi
echo ""

# Step 5: Final health check
echo "Step 5: Final health check..."
sleep 5

echo "Container Status:"
docker-compose ps
echo ""

echo "Testing endpoints:"
docker-compose exec -T blackbox curl -f --max-time 5 http://localhost:8000/health 2>&1 | head -5
echo ""

echo "Recent errors:"
docker-compose logs --tail=20 blackbox 2>&1 | grep -i "error\|exception" | tail -10 || echo "No recent errors"
echo ""

echo "=== RECOVERY COMPLETE ==="
echo ""
echo "If site is still down:"
echo "  1. Check logs: docker-compose logs -f"
echo "  2. Full restart: docker-compose restart"
echo "  3. Nuclear option: docker-compose down && docker-compose up -d"
echo ""
echo "Monitor with: ./monitor-performance.sh"
