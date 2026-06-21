#!/bin/bash
# scripts/backup_db.sh
# Run daily via cron: 0 2 * * * /path/to/scripts/backup_db.sh

DB_NAME="app_dev.db"
BACKUP_DIR="./backups"
RETENTION_DAYS=30

mkdir -p "$BACKUP_DIR"

BACKUP_NAME="$BACKUP_DIR/backup_$(date +%Y%m%d_%H%M%S).db"
sqlite3 "$DB_NAME" ".backup '$BACKUP_NAME'"

if [ $? -eq 0 ]; then
    echo "✅ Backup created: $BACKUP_NAME"
else
    echo "❌ Backup FAILED" && exit 1
fi

# Remove backups older than retention period
find "$BACKUP_DIR" -name "*.db" -mtime +"$RETENTION_DAYS" -delete
echo "🧹 Cleaned backups older than $RETENTION_DAYS days"
