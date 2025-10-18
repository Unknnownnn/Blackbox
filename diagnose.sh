#!/bin/bash
# BlackBox CTF Container Diagnostic Script (Linux)
# Run this to diagnose why the container is unhealthy
# Usage: chmod +x diagnose.sh && ./diagnose.sh

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  BlackBox CTF Container Diagnostics${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo -e "${YELLOW}Note: 'jq' not installed. Install with: sudo apt-get install jq${NC}"
    echo ""
fi

# 1. Container Status
echo -e "${YELLOW}[1/8] Checking Container Status...${NC}"
docker ps --filter name=blackbox-ctf --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""

# 2. Health Check Details
echo -e "${YELLOW}[2/8] Checking Health Check Details...${NC}"
HEALTH_STATUS=$(docker inspect --format='{{.State.Health.Status}}' blackbox-ctf 2>/dev/null)
FAILING_STREAK=$(docker inspect --format='{{.State.Health.FailingStreak}}' blackbox-ctf 2>/dev/null)

if [ -n "$HEALTH_STATUS" ]; then
    if [ "$HEALTH_STATUS" = "healthy" ]; then
        echo -e "Status: ${GREEN}$HEALTH_STATUS${NC}"
    else
        echo -e "Status: ${RED}$HEALTH_STATUS${NC}"
    fi
    echo "Failing Streak: $FAILING_STREAK"
    
    echo ""
    echo "Last 3 Health Check Results:"
    if command -v jq &> /dev/null; then
        docker inspect --format='{{json .State.Health.Log}}' blackbox-ctf | jq -r '.[-3:] | .[] | "  - Exit Code: \(.ExitCode) at \(.Start) | Output: \(.Output[:100])"'
    else
        docker inspect --format='{{range .State.Health.Log}}Exit Code: {{.ExitCode}} | Output: {{.Output}}{{"\n"}}{{end}}' blackbox-ctf | tail -n 6
    fi
else
    echo -e "${RED}Could not retrieve health check details${NC}"
fi
echo ""

# 3. Recent Logs
echo -e "${YELLOW}[3/8] Checking Recent Logs (Last 50 lines)...${NC}"
docker logs blackbox-ctf --tail 50 --timestamps
echo ""

# 4. Error Logs
echo -e "${YELLOW}[4/8] Searching for Errors in Logs...${NC}"
ERROR_COUNT=$(docker logs blackbox-ctf --tail 200 2>&1 | grep -cE "ERROR|Exception|Traceback|Failed|unhealthy")
if [ "$ERROR_COUNT" -gt 0 ]; then
    echo -e "${RED}Found $ERROR_COUNT error lines:${NC}"
    docker logs blackbox-ctf --tail 200 2>&1 | grep -E "ERROR|Exception|Traceback|Failed|unhealthy" | head -n 10 | while read -r line; do
        echo -e "  ${RED}$line${NC}"
    done
else
    echo -e "${GREEN}No obvious errors found in recent logs${NC}"
fi
echo ""

# 5. Test Health Endpoint
echo -e "${YELLOW}[5/8] Testing Health Endpoint...${NC}"
HEALTH_RESPONSE=$(docker exec blackbox-ctf curl -s http://localhost:8000/health 2>&1)
CURL_EXIT=$?

if [ $CURL_EXIT -eq 0 ]; then
    echo -e "${GREEN}Health endpoint response:${NC}"
    if command -v jq &> /dev/null; then
        echo "$HEALTH_RESPONSE" | jq
    else
        echo "$HEALTH_RESPONSE"
    fi
else
    echo -e "${RED}Failed to reach health endpoint!${NC}"
    echo "$HEALTH_RESPONSE"
fi
echo ""

# 6. Check Running Processes
echo -e "${YELLOW}[6/8] Checking Running Processes...${NC}"
PROCESS_COUNT=$(docker exec blackbox-ctf ps aux 2>&1 | grep -cE "gunicorn|python")
if [ "$PROCESS_COUNT" -gt 0 ]; then
    echo -e "${GREEN}Found Python/Gunicorn processes:${NC}"
    docker exec blackbox-ctf ps aux 2>&1 | grep -E "gunicorn|python" | while read -r line; do
        echo "  $line"
    done
else
    echo -e "${RED}WARNING: No Gunicorn processes found!${NC}"
fi
echo ""

# 7. Test Database Connection
echo -e "${YELLOW}[7/8] Testing Database Connection...${NC}"
DB_TEST=$(docker exec blackbox-ctf python -c "from app import create_app; from models import db; app = create_app(); app.app_context().push(); db.session.execute(db.text('SELECT 1')); print('DB OK')" 2>&1)
if echo "$DB_TEST" | grep -q "DB OK"; then
    echo -e "${GREEN}Database connection: OK${NC}"
else
    echo -e "${RED}Database connection: FAILED${NC}"
    echo "$DB_TEST"
fi
echo ""

# 8. Test Redis Connection
echo -e "${YELLOW}[8/8] Testing Redis Connection...${NC}"
REDIS_TEST=$(docker exec blackbox-cache redis-cli PING 2>&1)
if echo "$REDIS_TEST" | grep -q "PONG"; then
    echo -e "${GREEN}Redis connection: OK${NC}"
else
    echo -e "${RED}Redis connection: FAILED${NC}"
    echo "$REDIS_TEST"
fi
echo ""

# Summary
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  Diagnostic Summary${NC}"
echo -e "${CYAN}========================================${NC}"

CONTAINER_STATUS=$(docker inspect --format='{{.State.Status}}' blackbox-ctf 2>&1)
HEALTH_STATUS=$(docker inspect --format='{{.State.Health.Status}}' blackbox-ctf 2>&1)

if [ "$CONTAINER_STATUS" = "running" ]; then
    echo -e "Container Status: ${GREEN}$CONTAINER_STATUS${NC}"
else
    echo -e "Container Status: ${RED}$CONTAINER_STATUS${NC}"
fi

if [ "$HEALTH_STATUS" = "healthy" ]; then
    echo -e "Health Status: ${GREEN}$HEALTH_STATUS${NC}"
else
    echo -e "Health Status: ${RED}$HEALTH_STATUS${NC}"
fi

echo ""
echo -e "${YELLOW}Recommended Actions:${NC}"
if [ "$HEALTH_STATUS" != "healthy" ]; then
    echo "1. Check the errors in logs above"
    echo "2. Test services individually (database, redis)"
    echo "3. Try restarting: docker restart blackbox-ctf"
    echo "4. If persistent, rebuild: docker-compose build blackbox && docker-compose up -d"
else
    echo -e "${GREEN}Container appears healthy! If issues persist, check nginx logs.${NC}"
fi

echo ""
echo -e "${CYAN}For more details, see: DEBUGGING_UNHEALTHY_CONTAINER_LINUX.md${NC}"
echo ""

# Optional: Save output to file
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
OUTPUT_FILE="diagnostic_${TIMESTAMP}.log"
echo -e "${YELLOW}Tip: Run this script with output redirection to save results:${NC}"
echo "  ./diagnose.sh | tee $OUTPUT_FILE"
echo ""
