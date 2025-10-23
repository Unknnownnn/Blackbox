#!/bin/bash

echo "============================================"
echo "BlackBox CTF Platform - Complete Reset"
echo "============================================"
echo ""
echo "WARNING: This will DELETE ALL DATA!"
echo "This includes:"
echo "  - All database data (users, teams, challenges, submissions)"
echo "  - All uploaded files"
echo "  - All logs"
echo "  - Redis cache"
echo ""
echo "Press Ctrl+C to cancel, or Enter to continue..."
read

echo ""
echo "Stopping containers..."
docker-compose down -v

echo ""
echo "Removing old data..."
rm -rf .data/mysql/*
rm -rf .data/uploads/*
rm -rf .data/logs/*
rm -rf .data/redis/*

echo ""
echo "Building fresh containers (no cache)..."
docker-compose build --no-cache

echo ""
echo "Starting containers..."
docker-compose up -d

echo ""
echo "Waiting for services to initialize..."
echo "  - Database (MySQL)"
echo "  - Cache (Redis)"
echo "  - Application (CTF Platform)"
sleep 25

echo ""
echo "Checking database connection..."
for i in {1..5}; do
    docker-compose exec -T db mysql -u root -proot_password -e "SELECT 1;" > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "✓ Database is ready"
        break
    else
        echo "  Waiting for database... (attempt $i/5)"
        sleep 10
    fi
done

echo ""
echo "Creating database tables..."
docker-compose exec -T blackbox python -c "from app import create_app; from models import db; app = create_app(); app.app_context().push(); db.create_all(); print('✓ Tables created')"

echo ""
echo "Running database migrations..."

# Pipe SQL files from the host into the DB container's mysql client (avoid running mysql inside blackbox)
docker-compose exec -T db mysql -u root -proot_password ctf_platform < migrations/add_hints_and_team_requirements.sql 2>/dev/null || true
docker-compose exec -T db mysql -u root -proot_password ctf_platform < migrations/add_team_invites_and_attempts.sql 2>/dev/null || true
docker-compose exec -T db mysql -u root -proot_password ctf_platform < migrations/add_challenge_branching.sql 2>/dev/null || true
docker-compose exec -T db mysql -u root -proot_password ctf_platform < migrations/add_ctf_control.sql 2>/dev/null || true
docker-compose exec -T db mysql -u root -proot_password ctf_platform < migrations/add_event_config.sql 2>/dev/null || true
docker-compose exec -T db mysql -u root -proot_password ctf_platform < migrations/add_first_blood_and_dynamic_scoring.sql 2>/dev/null || true
docker-compose exec -T db mysql -u root -proot_password ctf_platform < migrations/add_container_orchestration.sql 2>/dev/null || true
docker-compose exec -T db mysql -u root -proot_password ctf_platform < migrations/add_docker_settings.sql 2>/dev/null || true
docker-compose exec -T db mysql -u root -proot_password ctf_platform < migrations/add_notifications.sql 2>/dev/null || true
docker-compose exec -T db mysql -u root -proot_password ctf_platform < migrations/add_notifications_play_sound.sql 2>/dev/null || true

echo "✓ Migrations completed"

echo ""
echo "Reset complete!"
echo ""
echo "============================================"
echo "Initial Setup Required"
echo "============================================"
echo ""
echo "Your BlackBox platform is ready for initial setup."
echo ""
echo "http://localhost:8000/setup"
echo ""
echo echo "============================================"
echo ""

