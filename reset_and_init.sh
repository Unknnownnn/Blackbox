#!/bin/bash
# Complete reset and fresh install script

echo "============================================"
echo "CTF Platform - Complete Reset & Fresh Install"
echo "============================================"
echo ""
echo "⚠️  WARNING: This will DELETE ALL DATA!"
echo "Press Ctrl+C to cancel, or Enter to continue..."
read

echo ""
echo "🛑 Stopping containers..."
docker-compose down -v

echo ""
echo "🗑️  Removing old data..."
rm -rf .data/mysql/*
rm -rf .data/uploads/*
rm -rf .data/logs/*
rm -rf .data/redis/*

echo ""
echo "🏗️  Building fresh containers..."
docker-compose build --no-cache

echo ""
echo "🚀 Starting containers..."
docker-compose up -d

echo ""
echo "⏳ Waiting for database to be ready (30 seconds)..."
sleep 30

echo ""
echo "🔍 Checking database health..."
docker-compose exec db mysql -u root -proot_password -e "SELECT 1;" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✓ Database is ready"
else
    echo "❌ Database is not ready. Waiting another 15 seconds..."
    sleep 15
fi

echo ""
echo "📊 Initializing database..."
docker-compose exec -T ctf python init_db.py

echo ""
echo "✅ Fresh installation complete!"
echo ""
echo "============================================"
echo "Default Admin Credentials:"
echo "============================================"
echo "Username: admin"
echo "Password: admin123"
echo ""
echo "Sample User Credentials:"
echo "Username: alice, bob, charlie, dave, eve, frank"
echo "Password: password123"
echo ""
echo "============================================"
echo "Access your CTF platform at:"
echo "http://localhost:8000"
echo "or"
echo "http://0.0.0.0:8000"
echo "============================================"
echo ""
echo "📝 Note: All tables including hints, settings, and team requirements are created automatically!"
echo ""
