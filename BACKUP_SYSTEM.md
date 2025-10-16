# Backup & Restore System

## Overview
Comprehensive backup and disaster recovery system for the CTF platform with automatic hourly backups and manual backup/restore capabilities.

## Features

### ✅ Automatic Backups
- **Frequency**: Every hour automatically
- **Retention**: 7 days (168 hourly backups)
- **Components**: Database, Uploads, Redis cache
- **Auto-cleanup**: Old backups automatically deleted

### ✅ Manual Backups
- Create on-demand backups anytime
- Through admin UI or command line
- Instant snapshot of current state

### ✅ Easy Restore
- One-click restore from admin UI
- Choose any backup to restore from
- Automatic application restart after restore

### ✅ Backup Management
- View all available backups
- See backup timestamps and sizes
- Download backups for offsite storage
- Delete old/unwanted backups

## Usage

### Admin UI (Recommended)

1. **Access Backup Management**
   - Navigate to: `Admin → Backups`
   - View all available backups
   - See statistics and latest backup time

2. **Create Manual Backup**
   - Click "Create Manual Backup" button
   - Wait for confirmation (1-5 minutes)
   - Backup appears in the list

3. **Restore from Backup**
   - Find the backup you want to restore
   - Click "Restore" button
   - Confirm the action (requires typing "YES")
   - Wait for restore to complete
   - Application automatically restarts

4. **Download Backup**
   - Click download icon next to backup
   - Backup downloaded as `.tar.gz` file
   - Store offsite for disaster recovery

5. **Delete Backup**
   - Click delete icon next to backup
   - Confirm deletion
   - Backup permanently removed

### Command Line

#### Create Backup
```bash
docker exec blackbox-backup /usr/local/bin/backup.sh
```

#### List Backups
```bash
docker exec blackbox-backup ls -lh /var/backups/ctf/
```

#### Restore Backup
```bash
# Interactive (asks for confirmation)
docker exec -it blackbox-backup /usr/local/bin/restore.sh backup_20251017_143000

# Automatic (no confirmation)
docker exec -e FORCE_RESTORE=1 blackbox-backup /usr/local/bin/restore.sh backup_20251017_143000

# Restart application after restore
docker compose restart blackbox cache
```

#### View Backup Logs
```bash
# Backup creation log
docker exec blackbox-backup tail -f /var/backups/ctf/backup.log

# Cron job log
docker exec blackbox-backup tail -f /var/backups/ctf/cron.log

# Restore log
docker exec blackbox-backup tail -f /var/backups/ctf/restore.log
```

## Backup Contents

Each backup includes:

1. **Database (database.sql.gz)**
   - All tables and data
   - Triggers, procedures, events
   - Compressed with gzip

2. **Uploads (uploads.tar.gz)**
   - All challenge files
   - User uploaded content
   - Compressed archive

3. **Redis Cache (redis.rdb)**
   - Cached data
   - Session information
   - Quick state recovery

4. **Metadata (metadata.json)**
   - Backup timestamp
   - Component sizes
   - Verification info

## Backup Location

- **Container Path**: `/var/backups/ctf/`
- **Docker Volume**: `backups`
- **Format**: `backup_YYYYMMDD_HHMMSS/`

### Access Backup Volume
```bash
# Copy backup to host
docker cp blackbox-backup:/var/backups/ctf/backup_20251017_143000 ./local-backup

# View backup volume
docker volume inspect hostingplatform_backups
```

## Configuration

### Environment Variables

Set in `docker-compose.yml` or `.env`:

```bash
# Maximum number of backups to keep (default: 168 = 7 days of hourly)
MAX_BACKUPS=168

# Database credentials (inherited from main config)
DATABASE_USER=blackbox_user
DATABASE_PASSWORD=blackbox_password
DATABASE_NAME=blackbox_ctf
MYSQL_ROOT_PASSWORD=root_password
```

### Change Backup Schedule

Edit the cron schedule in `docker-compose.yml` backup service:

```yaml
# Current: Every hour
echo '0 * * * * /usr/local/bin/backup.sh >> /var/backups/ctf/cron.log 2>&1'

# Every 2 hours
echo '0 */2 * * * /usr/local/bin/backup.sh >> /var/backups/ctf/cron.log 2>&1'

# Every 6 hours
echo '0 */6 * * * /usr/local/bin/backup.sh >> /var/backups/ctf/cron.log 2>&1'

# Daily at 2 AM
echo '0 2 * * * /usr/local/bin/backup.sh >> /var/backups/ctf/cron.log 2>&1'
```

Then restart: `docker compose restart backup`

## Disaster Recovery

### Scenario 1: Data Corruption

1. Go to Admin → Backups
2. Find last good backup
3. Click "Restore"
4. System automatically recovers

### Scenario 2: Complete System Loss

1. Reinstall/redeploy platform
2. Copy backup files to backup volume
3. Restore from backup via CLI or UI
4. System fully recovered

### Scenario 3: Offsite Backup

1. Download backups regularly from admin UI
2. Store on separate server/cloud storage
3. In case of server loss, restore from downloaded backup

```bash
# Upload backup to volume
docker cp backup_20251017_143000.tar.gz blackbox-backup:/var/backups/ctf/
docker exec blackbox-backup tar -xzf /var/backups/ctf/backup_20251017_143000.tar.gz -C /var/backups/ctf/
docker exec blackbox-backup rm /var/backups/ctf/backup_20251017_143000.tar.gz

# Restore
docker exec -e FORCE_RESTORE=1 blackbox-backup /usr/local/bin/restore.sh backup_20251017_143000
docker compose restart blackbox cache
```

## Troubleshooting

### Backup Service Not Running
```bash
docker ps | grep backup
docker logs blackbox-backup
docker compose restart backup
```

### Backup Failed
```bash
# Check logs
docker exec blackbox-backup cat /var/backups/ctf/backup.log

# Check disk space
docker exec blackbox-backup df -h /var/backups/ctf

# Manual backup with debug
docker exec blackbox-backup bash -x /usr/local/bin/backup.sh
```

### Restore Failed
```bash
# Check restore log
docker exec blackbox-backup cat /var/backups/ctf/restore.log

# Verify backup integrity
docker exec blackbox-backup ls -lh /var/backups/ctf/backup_YYYYMMDD_HHMMSS/

# Check database connection
docker exec blackbox-backup mysql -h db -u root -p -e "SHOW DATABASES;"
```

### Disk Space Issues
```bash
# Check backup volume size
docker exec blackbox-backup du -sh /var/backups/ctf/

# Reduce MAX_BACKUPS to keep fewer backups
# Edit docker-compose.yml and set MAX_BACKUPS=48 (2 days)

# Manually clean old backups
docker exec blackbox-backup find /var/backups/ctf -name "backup_*" -type d -mtime +7 -exec rm -rf {} \;
```

## Best Practices

1. **Regular Testing**: Test restore process monthly
2. **Offsite Backups**: Download and store backups elsewhere weekly
3. **Monitor Space**: Check backup volume size regularly
4. **Verify Backups**: Ensure backups are completing successfully
5. **Document Recovery**: Keep recovery procedures documented
6. **Pre-Event Backup**: Create manual backup before major CTF events
7. **Post-Event Backup**: Create manual backup after events end

## Backup Schedule Example

```
Hour 0:  Auto backup (retention: 7 days)
Hour 1:  Auto backup
Hour 2:  Auto backup
...
Hour 23: Auto backup

Week 1:  Manual backup → Download → Store offsite
Week 2:  Manual backup → Download → Store offsite
...

Before CTF: Manual backup
After CTF:  Manual backup
```

## Security Notes

- Backups contain sensitive data (flags, user info, passwords)
- Store offsite backups securely
- Encrypt downloaded backups if storing remotely
- Limit access to backup management (admin only)
- Backup volume is internal to Docker network
- Use strong database passwords

## Support

For issues or questions:
1. Check logs: `/var/backups/ctf/*.log`
2. Verify services: `docker compose ps`
3. Test manually: `docker exec blackbox-backup /usr/local/bin/backup.sh`
