#!/bin/bash
# Check database connection health and fix common issues

echo "=== Database Connection Diagnostics ==="
echo ""

# Check if database container is running
echo "1. Database Container Status:"
docker-compose ps db
echo ""

# Check database process list
echo "2. Database Connections:"
docker-compose exec -T db mysql -ublackbox_user -pblackbox_password -e "SHOW STATUS LIKE 'Threads_connected';" 2>&1
docker-compose exec -T db mysql -ublackbox_user -pblackbox_password -e "SHOW STATUS LIKE 'Max_used_connections';" 2>&1
docker-compose exec -T db mysql -ublackbox_user -pblackbox_password -e "SHOW VARIABLES LIKE 'max_connections';" 2>&1
echo ""

# Show current connections by user
echo "3. Active Connections by User:"
docker-compose exec -T db mysql -ublackbox_user -pblackbox_password -e "SELECT user, COUNT(*) as connections FROM information_schema.processlist GROUP BY user;" 2>&1
echo ""

# Check for locked tables
echo "4. Locked Tables:"
docker-compose exec -T db mysql -ublackbox_user -pblackbox_password -e "SHOW OPEN TABLES WHERE In_use > 0;" 2>&1
echo ""

# Check database errors
echo "5. Recent Database Errors:"
docker-compose logs --tail=50 db | grep -i "error\|warning" || echo "No recent errors"
echo ""

# Test connection from blackbox container
echo "6. Test Connection from App:"
docker-compose exec -T blackbox python -c "
from app import create_app, db
app = create_app()
with app.app_context():
    try:
        db.session.execute(db.text('SELECT 1'))
        print('✓ Database connection successful')
    except Exception as e:
        print(f'✗ Database connection failed: {e}')
" 2>&1
echo ""

# Check for long-running queries
echo "7. Long-Running Queries (>5s):"
docker-compose exec -T db mysql -ublackbox_user -pblackbox_password -e "
SELECT 
    id, user, host, db, command, time, state, 
    LEFT(info, 100) as query_preview
FROM information_schema.processlist 
WHERE command != 'Sleep' AND time > 5
ORDER BY time DESC;
" 2>&1
echo ""

echo "=== Recommended Actions ==="
if docker-compose exec -T db mysql -ublackbox_user -pblackbox_password -e "SHOW STATUS LIKE 'Threads_connected';" 2>&1 | grep -q "Threads_connected"; then
    CONNECTIONS=$(docker-compose exec -T db mysql -ublackbox_user -pblackbox_password -e "SHOW STATUS LIKE 'Threads_connected';" 2>&1 | awk 'NR==2 {print $2}')
    echo "Current connections: $CONNECTIONS"
    
    if [ "$CONNECTIONS" -gt 450 ]; then
        echo "⚠ WARNING: Close to max connections (500). Consider:"
        echo "  - Restart app to clear stale connections: docker-compose restart blackbox"
        echo "  - Increase max_connections in docker-compose.yml"
    elif [ "$CONNECTIONS" -gt 400 ]; then
        echo "⚠ CAUTION: High connection count. Monitor closely."
    else
        echo "✓ Connection count is healthy"
    fi
else
    echo "✗ Cannot connect to database"
    echo "Actions:"
    echo "  1. Check if database is running: docker-compose ps db"
    echo "  2. Check database logs: docker-compose logs db"
    echo "  3. Restart database: docker-compose restart db"
    echo "  4. Restart entire stack: docker-compose restart"
fi
