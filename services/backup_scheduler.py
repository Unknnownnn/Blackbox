"""
Automatic backup scheduler for the CTF platform.
Handles scheduled database backups based on configured frequency.
"""

import gzip
import json
import logging
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import pymysql
from apscheduler.schedulers.background import BackgroundScheduler

from models.settings import Settings

logger = logging.getLogger(__name__)


class BackupScheduler:
    """Manages automatic database backups"""
    
    def __init__(self, app=None):
        self.app = app
        self.scheduler = None
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize the backup scheduler with Flask app"""
        self.app = app
        self.scheduler = BackgroundScheduler(daemon=True)
        
        # Start the scheduler (schedule will be set on first settings access)
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Backup scheduler started (will schedule on first settings access)")
    
    def _schedule_backups(self):
        """Configure backup schedule based on settings"""
        try:
            frequency = Settings.get('backup_frequency', 'disabled')
        except Exception as e:
            # Database might not be ready yet, use default
            logger.warning(f"Could not read backup frequency setting: {e}")
            frequency = 'disabled'
        
        # Remove existing backup job if any
        if self.scheduler.get_job('auto_backup'):
            self.scheduler.remove_job('auto_backup')
        
        if frequency == 'disabled':
            logger.info("Automatic backups are disabled")
            return
        
        # Schedule based on frequency
        if frequency == 'hourly':
            self.scheduler.add_job(
                self.create_automatic_backup,
                'cron',
                minute=0,  # Every hour at :00
                id='auto_backup',
                replace_existing=True
            )
            logger.info("Automatic backups scheduled: Every hour at :00")
        
        elif frequency == 'daily':
            self.scheduler.add_job(
                self.create_automatic_backup,
                'cron',
                hour=2,
                minute=0,  # Daily at 2:00 AM
                id='auto_backup',
                replace_existing=True
            )
            logger.info("Automatic backups scheduled: Daily at 2:00 AM")
        
        elif frequency == 'weekly':
            self.scheduler.add_job(
                self.create_automatic_backup,
                'cron',
                day_of_week='sun',
                hour=2,
                minute=0,  # Sunday at 2:00 AM
                id='auto_backup',
                replace_existing=True
            )
            logger.info("Automatic backups scheduled: Weekly on Sunday at 2:00 AM")
        
        elif frequency == 'monthly':
            self.scheduler.add_job(
                self.create_automatic_backup,
                'cron',
                day=1,
                hour=2,
                minute=0,  # 1st day of month at 2:00 AM
                id='auto_backup',
                replace_existing=True
            )
            logger.info("Automatic backups scheduled: Monthly on 1st at 2:00 AM")
    
    def reschedule(self):
        """Reschedule backups (call after settings change)"""
        logger.info("Rescheduling automatic backups")
        self._schedule_backups()
    
    def create_automatic_backup(self):
        """Create an automatic backup"""
        logger.info("Starting automatic backup...")
        
        try:
            with self.app.app_context():
                # Get database connection info
                db_uri = self.app.config.get('SQLALCHEMY_DATABASE_URI')
                
                # Create backup directory
                backup_dir = Path(self.app.config.get('UPLOAD_FOLDER', 'static/uploads')) / 'backups'
                backup_dir.mkdir(parents=True, exist_ok=True)
                
                # Generate backup name
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_name = f'backup_auto_{timestamp}'
                backup_file = backup_dir / f'{backup_name}.sql.gz'
                
                # Export database to SQL dump
                parsed = urlparse(db_uri)
                conn = pymysql.connect(
                    host=parsed.hostname,
                    port=parsed.port or 3306,
                    user=parsed.username,
                    password=parsed.password,
                    database=parsed.path.lstrip('/')
                )
                
                cursor = conn.cursor()
                
                # Get all tables
                cursor.execute("SHOW TABLES")
                tables = [table[0] for table in cursor.fetchall()]
                
                # Create SQL dump
                sql_dump = []
                sql_dump.append(f"-- Automatic database backup: {backup_name}")
                sql_dump.append(f"-- Timestamp: {datetime.now().isoformat()}")
                sql_dump.append("SET FOREIGN_KEY_CHECKS=0;")
                
                for table in tables:
                    # Get CREATE TABLE statement
                    cursor.execute(f"SHOW CREATE TABLE `{table}`")
                    create_table = cursor.fetchone()[1]
                    sql_dump.append(f"\n-- Table: {table}")
                    sql_dump.append(f"DROP TABLE IF EXISTS `{table}`;")
                    sql_dump.append(create_table + ";")
                    
                    # Get table data
                    cursor.execute(f"SELECT * FROM `{table}`")
                    rows = cursor.fetchall()
                    
                    if rows:
                        cursor.execute(f"DESCRIBE `{table}`")
                        columns = [col[0] for col in cursor.fetchall()]
                        column_list = ', '.join([f'`{col}`' for col in columns])
                        
                        sql_dump.append(f"INSERT INTO `{table}` ({column_list}) VALUES")
                        
                        for i, row in enumerate(rows):
                            values = []
                            for value in row:
                                if value is None:
                                    values.append('NULL')
                                elif isinstance(value, (int, float)):
                                    values.append(str(value))
                                elif isinstance(value, bytes):
                                    values.append(f"'{value.decode('utf-8', errors='replace')}'")
                                else:
                                    # Escape single quotes
                                    escaped = str(value).replace("'", "''")
                                    values.append(f"'{escaped}'")
                            
                            row_sql = f"({', '.join(values)})"
                            if i < len(rows) - 1:
                                row_sql += ","
                            else:
                                row_sql += ";"
                            sql_dump.append(row_sql)
                
                sql_dump.append("\nSET FOREIGN_KEY_CHECKS=1;")
                
                cursor.close()
                conn.close()
                
                # Write compressed backup
                with gzip.open(backup_file, 'wt', encoding='utf-8') as f:
                    f.write('\n'.join(sql_dump))
                
                # Create metadata file
                metadata = {
                    'backup_name': backup_name,
                    'timestamp': datetime.now().isoformat(),
                    'size_mb': round(backup_file.stat().st_size / (1024 * 1024), 2),
                    'auto_backup': True,
                    'tables': len(tables)
                }
                
                metadata_file = backup_file.with_suffix('.json')
                with open(metadata_file, 'w') as f:
                    json.dump(metadata, f, indent=2)
                
                # Update last backup time
                Settings.set('last_auto_backup', datetime.now(), 'datetime', 'Last automatic backup')
                
                logger.info(f"Automatic backup created successfully: {backup_name}")
                logger.info(f"Backup size: {metadata['size_mb']} MB, Tables: {metadata['tables']}")
                
                # Keep only last 10 automatic backups
                self._cleanup_old_backups(backup_dir)
        
        except Exception as e:
            logger.error(f"Automatic backup failed: {str(e)}", exc_info=True)
    
    def _cleanup_old_backups(self, backup_dir):
        """Keep only the most recent automatic backups"""
        try:
            max_backups = 10  # Keep last 10 automatic backups
            
            # Get all automatic backup files
            auto_backups = sorted(
                backup_dir.glob('backup_auto_*.sql.gz'),
                key=lambda f: f.stat().st_mtime,
                reverse=True
            )
            
            # Remove old backups
            for backup_file in auto_backups[max_backups:]:
                metadata_file = backup_file.with_suffix('.json')
                
                backup_file.unlink()
                if metadata_file.exists():
                    metadata_file.unlink()
                
                logger.info(f"Removed old automatic backup: {backup_file.name}")
        
        except Exception as e:
            logger.error(f"Failed to cleanup old backups: {str(e)}")


# Global scheduler instance
backup_scheduler = None


def init_backup_scheduler(app):
    """Initialize the global backup scheduler"""
    global backup_scheduler
    backup_scheduler = BackupScheduler(app)
    return backup_scheduler
