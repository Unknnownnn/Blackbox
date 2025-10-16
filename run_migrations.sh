echo "============================================"
echo "BlackBox Migrations"
echo "============================================"
echo ""

# Get database container ID
DB_CONTAINER=$(docker-compose ps -q db)

if [ -z "$DB_CONTAINER" ]; then
    echo "Error: Database container not found!"
    echo "Make sure docker-compose is running"
    exit 1
fi

echo "✓ Found database container: $DB_CONTAINER"
echo ""

# Backup database
echo "Creating backup..."
docker-compose exec db mysqldump -u root -proot_password ctf_platform > backup_phase12_13_$(date +%Y%m%d_%H%M%S).sql
echo "✓ Backup created"
echo ""

# Migration 1: CTF Control
echo "Running Migration 1: CTF Control..."
docker cp migrations/add_ctf_control.sql $DB_CONTAINER:/tmp/migration1.sql
docker-compose exec db mysql -u root -proot_password ctf_platform -e "SOURCE /tmp/migration1.sql"

if [ $? -eq 0 ]; then
    echo "Migration 1 completed successfully"
else
    echo "Migration 1 failed!"
    exit 1
fi
echo ""

# Migration 2: Hints & Team Requirements
echo "Running Migration 2: Hints & Team Requirements..."
docker cp migrations/add_hints_and_team_requirements.sql $DB_CONTAINER:/tmp/migration2.sql
docker-compose exec db mysql -u root -proot_password ctf_platform -e "SOURCE /tmp/migration2.sql"

if [ $? -eq 0 ]; then
    echo "Migration 2 completed successfully"
else
    echo "Migration 2 failed!"
    exit 1
fi
echo ""

# Verify migrations
echo "Verifying migrations..."
echo ""

echo "Checking settings table..."
docker-compose exec db mysql -u root -proot_password -e "SELECT COUNT(*) as count FROM ctf_platform.settings;" | grep -q "[0-9]"
if [ $? -eq 0 ]; then
    echo "Settings table exists"
else
    echo "Settings table not found"
fi

echo "Checking challenges.is_enabled column..."
docker-compose exec db mysql -u root -proot_password -e "DESCRIBE ctf_platform.challenges;" | grep -q "is_enabled"
if [ $? -eq 0 ]; then
    echo "is_enabled column exists"
else
    echo "is_enabled column not found"
fi

echo "Checking challenges.requires_team column..."
docker-compose exec db mysql -u root -proot_password -e "DESCRIBE ctf_platform.challenges;" | grep -q "requires_team"
if [ $? -eq 0 ]; then
    echo "requires_team column exists"
else
    echo "requires_team column not found"
fi

echo "Checking hints table..."
docker-compose exec db mysql -u root -proot_password -e "SHOW TABLES FROM ctf_platform LIKE 'hints';" | grep -q "hints"
if [ $? -eq 0 ]; then
    echo "Hints table exists"
else
    echo "Hints table not found"
fi

echo "Checking hint_unlocks table..."
docker-compose exec db mysql -u root -proot_password -e "SHOW TABLES FROM ctf_platform LIKE 'hint_unlocks';" | grep -q "hint_unlocks"
if [ $? -eq 0 ]; then
    echo "Hint_unlocks table exists"
else
    echo "Hint_unlocks table not found"
fi

echo ""
echo "============================================"
echo "Migration Summary"
echo "============================================"
docker-compose exec db mysql -u root -proot_password -e "
SELECT 
    'Settings' as TableName, COUNT(*) as RowCount 
FROM ctf_platform.settings
UNION ALL
SELECT 'Hints', COUNT(*) FROM ctf_platform.hints
UNION ALL
SELECT 'Hint Unlocks', COUNT(*) FROM ctf_platform.hint_unlocks;
"

echo ""
echo "============================================"
echo "Migrations completed!"
echo "============================================"
echo ""
echo "Next steps:"
echo "1. Rebuild containers: docker-compose down && docker-compose up --build -d"
echo "2. Test the application"
echo "3. Check PHASE_12_SUMMARY.md and PHASE_13_SUMMARY.md for details"
echo ""
