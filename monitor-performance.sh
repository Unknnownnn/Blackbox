#!/bin/bash
# Monitor CTF platform performance under high load

echo "=== BlackBox CTF Performance Monitor ==="
echo "Monitoring 200+ user load..."
echo ""

while true; do
    clear
    echo "=== Time: $(date) ==="
    echo ""
    
    echo "=== Container Status ==="
    docker-compose ps
    echo ""
    
    echo "=== Resource Usage ==="
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"
    echo ""
    
    echo "=== Database Connections ==="
    docker-compose exec -T db mysql -u${DATABASE_USER:-blackbox_user} -p${DATABASE_PASSWORD:-blackbox_password} -e "SHOW STATUS LIKE 'Threads_connected';" 2>/dev/null || echo "Cannot connect to DB"
    docker-compose exec -T db mysql -u${DATABASE_USER:-blackbox_user} -p${DATABASE_PASSWORD:-blackbox_password} -e "SHOW STATUS LIKE 'Max_used_connections';" 2>/dev/null
    echo ""
    
    echo "=== Redis Info ==="
    docker-compose exec -T cache redis-cli INFO clients | grep connected_clients
    docker-compose exec -T cache redis-cli INFO memory | grep used_memory_human
    echo ""
    
    echo "=== Recent Errors (last 10 lines) ==="
    docker-compose logs --tail=10 blackbox 2>&1 | grep -i "error\|exception\|timeout" || echo "No recent errors"
    echo ""
    
    echo "Press Ctrl+C to exit. Refreshing in 5 seconds..."
    sleep 5
done
