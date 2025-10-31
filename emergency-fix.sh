#!/bin/bash
# Emergency fix for frozen Flask workers

echo "=== EMERGENCY RECOVERY ==="
echo "Detecting frozen workers and restarting..."
echo ""

# Check if blackbox is frozen (0% CPU)
CPU=$(docker stats --no-stream --format "{{.CPUPerc}}" blackbox-ctf | sed 's/%//')
echo "Current CPU usage: ${CPU}%"

if (( $(echo "$CPU < 0.5" | bc -l) )); then
    echo "⚠️  WARNING: Flask app appears frozen (CPU < 0.5%)"
    echo ""
    
    # Check worker processes
    echo "=== Checking Worker Processes ==="
    docker-compose exec -T blackbox ps aux | grep gunicorn || echo "Cannot check workers"
    echo ""
    
    # Force restart Flask app
    echo "🔄 Restarting Flask application..."
    docker-compose restart blackbox
    
    # Wait for startup
    echo "⏳ Waiting 15 seconds for restart..."
    sleep 15
    
    # Check if it's back
    echo ""
    echo "=== Status After Restart ==="
    docker-compose ps blackbox
    
    NEW_CPU=$(docker stats --no-stream --format "{{.CPUPerc}}" blackbox-ctf | sed 's/%//')
    echo "New CPU usage: ${NEW_CPU}%"
    
    # Check health endpoint
    echo ""
    echo "=== Testing Health Endpoint ==="
    docker-compose exec -T nginx curl -f http://blackbox:8000/health && echo "✅ App is healthy" || echo "❌ App still not responding"
    
else
    echo "✅ App appears to be running normally (CPU: ${CPU}%)"
fi

echo ""
echo "=== Current Resource Usage ==="
docker stats --no-stream

echo ""
echo "=== Recent Errors ==="
docker-compose logs --tail=30 blackbox | grep -i "error\|exception\|timeout" || echo "No recent errors"

echo ""
echo "=== Complete ===="
