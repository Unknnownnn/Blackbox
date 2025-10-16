#!/bin/bash

# Restore script for CTF Platform
# Restores database, uploads, and Redis data from a backup

set -e

BACKUP_DIR="/var/backups/ctf"

# MySQL credentials from environment
DB_HOST="${DB_HOST:-db}"
DB_USER="${DATABASE_USER:-blackbox_user}"
DB_PASSWORD="${DATABASE_PASSWORD:-blackbox_password}"
DB_NAME="${DATABASE_NAME:-blackbox_ctf}"
ROOT_PASSWORD="${MYSQL_ROOT_PASSWORD:-root_password}"

# Check if backup name is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <backup_name>"
    echo ""
    echo "Available backups:"
    find "${BACKUP_DIR}" -maxdepth 1 -type d -name "backup_*" | sort -r | head -20 | xargs -n1 basename
    exit 1
fi

BACKUP_NAME="$1"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

# Validate backup exists
if [ ! -d "${BACKUP_PATH}" ]; then
    echo "Error: Backup '${BACKUP_NAME}' not found at ${BACKUP_PATH}"
    exit 1
fi

echo "==========================================="
echo "WARNING: This will restore from backup and"
echo "OVERWRITE ALL CURRENT DATA!"
echo "==========================================="
echo "Backup: ${BACKUP_NAME}"
echo "Location: ${BACKUP_PATH}"
echo ""

# Check what will be restored
if [ -f "${BACKUP_PATH}/metadata.json" ]; then
    echo "Backup contents:"
    cat "${BACKUP_PATH}/metadata.json" | grep -E '(timestamp|database|uploads|redis)' || true
    echo ""
fi

# Confirmation (skip if FORCE_RESTORE=1)
if [ "${FORCE_RESTORE}" != "1" ]; then
    echo "Type 'YES' to continue with restore:"
    read CONFIRM
    if [ "${CONFIRM}" != "YES" ]; then
        echo "Restore cancelled."
        exit 0
    fi
fi

echo "Starting restore..." | tee -a "${BACKUP_DIR}/restore.log"
echo "Time: $(date)" | tee -a "${BACKUP_DIR}/restore.log"

# Restore MySQL database
if [ -f "${BACKUP_PATH}/database.sql.gz" ]; then
    echo "Restoring MySQL database..." | tee -a "${BACKUP_DIR}/restore.log"
    
    # Drop and recreate database
    mysql -h"${DB_HOST}" -uroot -p"${ROOT_PASSWORD}" -e "DROP DATABASE IF EXISTS ${DB_NAME};" 2>/dev/null || true
    mysql -h"${DB_HOST}" -uroot -p"${ROOT_PASSWORD}" -e "CREATE DATABASE ${DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    mysql -h"${DB_HOST}" -uroot -p"${ROOT_PASSWORD}" -e "GRANT ALL PRIVILEGES ON ${DB_NAME}.* TO '${DB_USER}'@'%';"
    
    # Restore from backup
    if gunzip < "${BACKUP_PATH}/database.sql.gz" | mysql -h"${DB_HOST}" -u"${DB_USER}" -p"${DB_PASSWORD}" "${DB_NAME}"; then
        echo "✓ Database restored successfully" | tee -a "${BACKUP_DIR}/restore.log"
    else
        echo "✗ Database restore failed!" | tee -a "${BACKUP_DIR}/restore.log"
        exit 1
    fi
else
    echo "⚠ No database backup found, skipping" | tee -a "${BACKUP_DIR}/restore.log"
fi

# Restore uploads
if [ -f "${BACKUP_PATH}/uploads.tar.gz" ]; then
    echo "Restoring uploads..." | tee -a "${BACKUP_DIR}/restore.log"
    rm -rf /var/uploads/*
    tar -xzf "${BACKUP_PATH}/uploads.tar.gz" -C /var/uploads/
    echo "✓ Uploads restored successfully" | tee -a "${BACKUP_DIR}/restore.log"
else
    echo "⚠ No uploads backup found, skipping" | tee -a "${BACKUP_DIR}/restore.log"
fi

# Restore Redis data
if [ -f "${BACKUP_PATH}/redis.rdb" ]; then
    echo "Restoring Redis data..." | tee -a "${BACKUP_DIR}/restore.log"
    redis-cli -h cache SHUTDOWN NOSAVE 2>/dev/null || true
    sleep 2
    cp "${BACKUP_PATH}/redis.rdb" /var/redis/dump.rdb
    # Redis will be restarted automatically by docker
    echo "✓ Redis data copied (will load on next start)" | tee -a "${BACKUP_DIR}/restore.log"
else
    echo "⚠ No Redis backup found, skipping" | tee -a "${BACKUP_DIR}/restore.log"
fi

echo "==========================================="
echo "✓ Restore completed successfully!"
echo "Backup: ${BACKUP_NAME}"
echo "Time: $(date)"
echo "==========================================="
echo ""
echo "NOTE: Please restart the application containers:"
echo "  docker-compose restart blackbox cache"

exit 0
