#!/bin/bash

# Backup script for CTF Platform
# Creates timestamped backups of database, uploads, and Redis data

set -e

BACKUP_DIR="/var/backups/ctf"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="backup_${TIMESTAMP}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

# MySQL credentials from environment
DB_HOST="${DB_HOST:-db}"
DB_USER="${DATABASE_USER:-blackbox_user}"
DB_PASSWORD="${DATABASE_PASSWORD:-blackbox_password}"
DB_NAME="${DATABASE_NAME:-ctf_platform}"

# Maximum number of backups to keep
MAX_BACKUPS="${MAX_BACKUPS:-168}"  # Keep 1 week of hourly backups (24*7)

# Create backup directory
mkdir -p "${BACKUP_PATH}"

echo "===========================================" | tee -a "${BACKUP_DIR}/backup.log"
echo "Starting backup: ${BACKUP_NAME}" | tee -a "${BACKUP_DIR}/backup.log"
echo "Time: $(date)" | tee -a "${BACKUP_DIR}/backup.log"
echo "===========================================" | tee -a "${BACKUP_DIR}/backup.log"

# Backup MySQL database
echo "Backing up MySQL database..." | tee -a "${BACKUP_DIR}/backup.log"
if mysqldump -h"${DB_HOST}" -u"${DB_USER}" -p"${DB_PASSWORD}" "${DB_NAME}" \
    --single-transaction \
    --routines \
    --triggers \
    --events \
    --quick \
    --lock-tables=false \
    | gzip > "${BACKUP_PATH}/database.sql.gz"; then
    echo "✓ Database backup completed" | tee -a "${BACKUP_DIR}/backup.log"
else
    echo "✗ Database backup failed!" | tee -a "${BACKUP_DIR}/backup.log"
    exit 1
fi

# Backup uploads directory
echo "Backing up uploads..." | tee -a "${BACKUP_DIR}/backup.log"
if [ -d "/var/uploads" ]; then
    tar -czf "${BACKUP_PATH}/uploads.tar.gz" -C /var/uploads . 2>/dev/null || true
    echo "✓ Uploads backup completed" | tee -a "${BACKUP_DIR}/backup.log"
else
    echo "⚠ No uploads directory found" | tee -a "${BACKUP_DIR}/backup.log"
fi

# Backup Redis data (save snapshot first)
echo "Backing up Redis data..." | tee -a "${BACKUP_DIR}/backup.log"
if redis-cli -h cache SAVE > /dev/null 2>&1; then
    if [ -f "/var/redis/dump.rdb" ]; then
        cp /var/redis/dump.rdb "${BACKUP_PATH}/redis.rdb"
        echo "✓ Redis backup completed" | tee -a "${BACKUP_DIR}/backup.log"
    else
        echo "⚠ Redis dump file not found" | tee -a "${BACKUP_DIR}/backup.log"
    fi
else
    echo "⚠ Redis backup skipped (could not connect)" | tee -a "${BACKUP_DIR}/backup.log"
fi

# Create backup metadata
cat > "${BACKUP_PATH}/metadata.json" <<EOF
{
    "backup_name": "${BACKUP_NAME}",
    "timestamp": "$(date -Iseconds)",
    "database": "${DB_NAME}",
    "components": {
        "database": $([ -f "${BACKUP_PATH}/database.sql.gz" ] && echo "true" || echo "false"),
        "uploads": $([ -f "${BACKUP_PATH}/uploads.tar.gz" ] && echo "true" || echo "false"),
        "redis": $([ -f "${BACKUP_PATH}/redis.rdb" ] && echo "true" || echo "false")
    },
    "sizes": {
        "database_mb": "$(du -m "${BACKUP_PATH}/database.sql.gz" 2>/dev/null | cut -f1 || echo 0)",
        "uploads_mb": "$(du -m "${BACKUP_PATH}/uploads.tar.gz" 2>/dev/null | cut -f1 || echo 0)",
        "redis_mb": "$(du -m "${BACKUP_PATH}/redis.rdb" 2>/dev/null | cut -f1 || echo 0)"
    }
}
EOF

# Calculate total backup size
BACKUP_SIZE=$(du -sh "${BACKUP_PATH}" | cut -f1)
echo "Total backup size: ${BACKUP_SIZE}" | tee -a "${BACKUP_DIR}/backup.log"

# Clean up old backups (keep only MAX_BACKUPS most recent)
echo "Cleaning up old backups..." | tee -a "${BACKUP_DIR}/backup.log"
BACKUP_COUNT=$(find "${BACKUP_DIR}" -maxdepth 1 -type d -name "backup_*" | wc -l)
if [ "${BACKUP_COUNT}" -gt "${MAX_BACKUPS}" ]; then
    OLD_BACKUPS=$(find "${BACKUP_DIR}" -maxdepth 1 -type d -name "backup_*" | sort | head -n -${MAX_BACKUPS})
    echo "${OLD_BACKUPS}" | xargs rm -rf
    REMOVED_COUNT=$(echo "${OLD_BACKUPS}" | wc -l)
    echo "✓ Removed ${REMOVED_COUNT} old backup(s)" | tee -a "${BACKUP_DIR}/backup.log"
else
    echo "✓ No old backups to remove (${BACKUP_COUNT}/${MAX_BACKUPS})" | tee -a "${BACKUP_DIR}/backup.log"
fi

echo "===========================================" | tee -a "${BACKUP_DIR}/backup.log"
echo "✓ Backup completed successfully: ${BACKUP_NAME}" | tee -a "${BACKUP_DIR}/backup.log"
echo "Location: ${BACKUP_PATH}" | tee -a "${BACKUP_DIR}/backup.log"
echo "===========================================" | tee -a "${BACKUP_DIR}/backup.log"

exit 0
