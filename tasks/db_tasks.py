import os
import shutil
import logging
from datetime import datetime
from config import settings
from .celery_app import celery_app

logger = logging.getLogger("retention_core.db_tasks")

@celery_app.task(name="tasks.backup_database", bind=True, max_retries=3)
def backup_database_task(self):
    """
    Safely backs up the SQLite database to a timestamped file.
    Designed for scaling safely without blocking API reads.
    """
    try:
        db_path = settings.database_url.replace("sqlite:///", "")
        if not os.path.exists(db_path):
            logger.warning(f"Database file not found at {db_path}")
            return "No database to backup."
            
        backup_dir = os.path.join(settings.data_root, "backups")
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"retention_core_{timestamp}.db.bak")
        
        # In SQLite, using shutil.copy2 on an active DB is acceptable for simple backups,
        # but using the native .backup() method is safer. For this task, shutil is enough 
        # for a standard SQLite deployment.
        import sqlite3
        def progress(status, remaining, total):
            logger.info(f"Copied {total-remaining} of {total} pages...")
            
        with sqlite3.connect(db_path) as src, sqlite3.connect(backup_path) as dst:
            src.backup(dst, pages=1000, progress=progress)
            
        logger.info(f"Database backup completed successfully: {backup_path}")
        return f"Backed up to {backup_path}"
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        raise self.retry(exc=e, countdown=60)
