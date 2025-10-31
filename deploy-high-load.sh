#!/bin/bash
# Deploy high-load optimized configuration for 200+ users

echo "=== BlackBox CTF High-Load Deployment ==="
echo "This will restart services with optimizations for 200+ concurrent users"
echo ""

# Stop services
echo "Stopping current services..."
docker-compose down

# Remove old containers (optional, preserves data)
echo "Removing old containers..."
docker-compose rm -f

# Rebuild with new configuration
echo "Building with optimized settings..."
docker-compose build --no-cache blackbox

# Start services
echo "Starting optimized services..."
docker-compose up -d

# Wait for services to be ready
echo ""
echo "Waiting for services to start..."
sleep 10

# Check status
echo ""
echo "=== Service Status ==="
docker-compose ps

echo ""
echo "=== Resource Limits ==="
echo "Workers: 8 (increased from 4)"
echo "Worker connections: 2000 per worker (16,000 total concurrent)"
echo "DB connections: 500 max (8 workers × 50 connections per worker = 400 used)"
echo "Redis: 2GB memory, 20,000 max clients"
echo "Nginx: 4096 worker connections"
echo ""

# Show logs
echo "=== Recent Logs ==="
docker-compose logs --tail=50 blackbox

echo ""
echo "=== Deployment Complete ==="
echo "Monitor with: docker-compose logs -f"
echo "Check stats: docker stats"
echo ""
