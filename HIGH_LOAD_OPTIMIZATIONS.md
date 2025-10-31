# High-Load Optimization Summary

## Problem
Website crashes every 5-10 minutes with 200+ concurrent users (worked fine with 50-60 users).

## Root Causes Identified
1. **Insufficient workers**: 4 workers couldn't handle 200+ users
2. **Database connection exhaustion**: Only 20 persistent connections (4 workers × 5 connections)
3. **Worker restarts**: Gunicorn restarting every 10,000 requests caused brief outages
4. **Redis connection limits**: 10,000 max clients insufficient
5. **Nginx connection limits**: 1,024 worker connections too low
6. **Short timeouts**: 60-120 second timeouts caused 504 errors under load

## Fixes Applied

### 1. Gunicorn Workers (gunicorn.conf.py)
- **Workers**: 4 → 8 (handles more concurrent load)
- **Worker connections**: 1,000 → 2,000 per worker (16,000 total concurrent)
- **Timeout**: 120s → 300s (prevents worker timeout under high load)
- **Max requests**: 10,000 → 50,000 (reduces frequent restarts)
- **Keepalive**: 5s → 10s (reduces connection overhead)

**Capacity**: 8 workers × 2,000 connections = **16,000 concurrent connections**

### 2. Database Connection Pool (config.py)
- **Pool size**: 5 → 20 per worker
- **Max overflow**: 10 → 30 per worker
- **Total capacity**: 8 workers × 50 connections = **400 database connections**
- **Pool timeout**: 30s → 60s (more patience under load)
- **Pool recycle**: 3600s → 1800s (faster connection refresh)

### 3. Database Server (docker-compose.yml)
- **Max connections**: 300 → 500
- **InnoDB buffer pool**: 256MB → 512MB
- **Added optimizations**:
  - `innodb-log-file-size=128M`
  - `innodb-flush-log-at-trx-commit=2` (better performance)
  - `innodb-flush-method=O_DIRECT` (bypass OS cache)

### 4. Redis (docker-compose.yml)
- **Max memory**: 1GB → 2GB
- **Max clients**: 10,000 → 20,000
- **TCP backlog**: Added 511
- **Timeout**: Added 300s

### 5. Nginx (nginx.conf)
- **Worker connections**: 1,024 → 4,096
- **Keepalive**: 32 → 64 connections
- **Keepalive requests**: Added 1,000
- **Proxy timeouts**: Added 300s for all operations
- **Keepalive timeout**: Added 60s

## Expected Performance

### Before Optimization
- **Concurrent users**: 50-60
- **Database connections**: 20-60 (pool exhaustion)
- **Nginx capacity**: ~1,000 connections
- **Worker crashes**: Every 10,000 requests
- **Result**: Crashes every 5-10 minutes with 200+ users

### After Optimization
- **Concurrent users**: 200-500+
- **Database connections**: Up to 400 (with headroom)
- **Nginx capacity**: ~4,000 connections
- **Worker stability**: Restarts every 50,000 requests
- **Result**: Stable under 200+ concurrent load

## Deployment Instructions

### Quick Deploy (Recommended)
```bash
# Make script executable
chmod +x deploy-high-load.sh

# Run deployment
./deploy-high-load.sh
```

### Manual Deployment
```bash
# Stop current services
docker-compose down

# Rebuild with new configuration
docker-compose build --no-cache blackbox

# Start optimized services
docker-compose up -d

# Check status
docker-compose ps
docker-compose logs -f
```

## Monitoring Commands

### Real-time Monitoring
```bash
# Run performance monitor
chmod +x monitor-performance.sh
./monitor-performance.sh

# Or manual monitoring:
watch -n 5 'docker stats --no-stream'
```

### Check for Issues
```bash
# Check if workers are restarting
docker-compose logs blackbox | grep -i "worker\|timeout\|killed"

# Check database connections
docker-compose exec db mysql -u blackbox_user -p blackbox_password \
  -e "SHOW STATUS LIKE 'Threads_connected';"

# Check Redis clients
docker-compose exec cache redis-cli INFO clients

# Check for 504 errors
docker-compose logs nginx | grep "504"

# Check resource usage
docker stats
```

### Verify Configuration
```bash
# Check worker count
docker-compose exec blackbox ps aux | grep gunicorn | wc -l
# Should show 9 (1 master + 8 workers)

# Check database max connections
docker-compose exec db mysql -u root -p -e "SHOW VARIABLES LIKE 'max_connections';"
# Should show 500

# Check Redis max clients
docker-compose exec cache redis-cli CONFIG GET maxclients
# Should show 20000
```

## Capacity Planning

### Current Configuration Supports
- **200-500 concurrent users**
- **16,000 simultaneous connections** (nginx + gunicorn)
- **400 database connections**
- **20,000 Redis clients**

### If You Need More (1000+ users)
1. **Increase workers**: Set `WORKERS=16` in docker-compose.yml
2. **Add more memory**: Increase DB buffer pool and Redis maxmemory
3. **Scale horizontally**: Add load balancer + multiple app instances
4. **Database tuning**: Consider read replicas or connection pooler (PgBouncer-style)

## Troubleshooting

### Still Getting 504 Errors?
```bash
# Check gunicorn timeout
docker-compose logs blackbox | grep "timeout"

# Increase timeout further in gunicorn.conf.py:
# timeout = 600  # 10 minutes
```

### Database Connection Errors?
```bash
# Check current connections
docker-compose exec db mysql -u root -p \
  -e "SHOW PROCESSLIST;"

# If hitting 500 limit, increase in docker-compose.yml:
# '--max_connections=1000'
```

### Out of Memory?
```bash
# Check memory usage
docker stats

# Add resource limits in docker-compose.yml:
# deploy:
#   resources:
#     limits:
#       memory: 4G
#     reservations:
#       memory: 2G
```

### Workers Still Dying?
```bash
# Check for OOM kills
dmesg | grep -i "out of memory\|oom"

# Reduce workers if low memory:
# WORKERS=6
```

## Health Checks

### Before Competition
```bash
# 1. Verify all services running
docker-compose ps

# 2. Check worker count
docker-compose exec blackbox ps aux | grep gunicorn

# 3. Test database connection
docker-compose exec blackbox python -c "from app import db; print('DB OK')"

# 4. Check Redis
docker-compose exec cache redis-cli ping

# 5. Load test (optional)
# Use Apache Bench or similar:
# ab -n 10000 -c 200 http://localhost/
```

### During Competition
```bash
# Monitor dashboard
./monitor-performance.sh

# Watch for errors
docker-compose logs -f blackbox | grep -i error

# Check if workers are healthy
docker-compose exec blackbox ps aux | grep gunicorn
```

## Performance Benchmarks

### Expected Response Times (200 users)
- **Login/Register**: < 500ms
- **View challenges**: < 200ms
- **Submit flag**: < 300ms
- **Scoreboard**: < 500ms (with caching)
- **Static files**: < 50ms

### Warning Signs
- Response times > 2 seconds
- Database connections > 450
- Redis clients > 18,000
- Worker restarts in logs
- 504 errors in nginx logs

## Summary of Changes
| Component | Before | After | Improvement |
|-----------|--------|-------|-------------|
| Workers | 4 | 8 | 2x capacity |
| Worker connections | 1,000 | 2,000 | 2x per worker |
| DB connections | 60 (4×15) | 400 (8×50) | 6.7x capacity |
| DB max conn | 300 | 500 | 1.7x |
| Redis memory | 1GB | 2GB | 2x |
| Redis clients | 10,000 | 20,000 | 2x |
| Nginx connections | 1,024 | 4,096 | 4x |
| Worker timeout | 120s | 300s | 2.5x |
| Max requests | 10,000 | 50,000 | 5x stability |

**Overall Capacity: 4-5x improvement (50-60 users → 200-500+ users)**
