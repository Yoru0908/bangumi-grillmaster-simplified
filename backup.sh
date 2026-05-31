#!/bin/bash
DB=/Users/yoru/data/bangumi-grillmaster/app.db
BACKUP_DIR=/Users/yoru/data/bangumi-grillmaster/backups
mkdir -p $BACKUP_DIR
CHECK=$(sqlite3 $DB "PRAGMA integrity_check;")
if [ "$CHECK" != "ok" ]; then
    echo "INTEGRITY FAILED: $CHECK" >&2
    exit 1
fi
sqlite3 $DB ".backup $BACKUP_DIR/app_$(date +%Y%m%d_%H%M).db"
ls -t $BACKUP_DIR/app_*.db 2>/dev/null | tail -n +25 | xargs rm -f
echo "BACKUP OK"
