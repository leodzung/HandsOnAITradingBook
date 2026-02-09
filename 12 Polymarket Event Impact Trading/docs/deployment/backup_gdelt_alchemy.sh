#!/bin/bash
# GDELT and Alchemy Database Backup Script
# Run manually or via cron: 0 0 * * * /path/to/backup_gdelt_alchemy.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="$SCRIPT_DIR/data"
BACKUP_DIR="$SCRIPT_DIR/backups/collectors"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p "$BACKUP_DIR"

echo "=== GDELT & Alchemy Database Backup: $DATE ==="

# Backup collector databases using SQLite's backup command (safe for active DBs)
for db in gdelt_news.db gdelt_events.db alchemy_trades.db; do
    if [ -f "$DATA_DIR/$db" ]; then
        BACKUP_FILE="$BACKUP_DIR/${db%.db}_$DATE.db"
        echo "Backing up $db..."
        sqlite3 "$DATA_DIR/$db" ".backup '$BACKUP_FILE'" 2>/dev/null || {
            # Fallback to copy if sqlite backup fails
            echo "  SQLite backup failed, using copy..."
            cp "$DATA_DIR/$db" "$BACKUP_FILE"
        }

        # Compress large backups
        SIZE=$(stat -f%z "$BACKUP_FILE" 2>/dev/null || stat -c%s "$BACKUP_FILE")
        if [ "$SIZE" -gt 50000000 ]; then  # >50MB
            echo "  Compressing (${SIZE} bytes)..."
            gzip "$BACKUP_FILE"
            BACKUP_FILE="$BACKUP_FILE.gz"
        fi

        echo "  Created: $(basename $BACKUP_FILE)"
    else
        echo "Skipping $db (not found)"
    fi
done

# Cleanup old backups (keep last 14 days for collectors)
echo "Cleaning up old backups..."
find "$BACKUP_DIR" -name "*.db" -mtime +14 -delete 2>/dev/null || true
find "$BACKUP_DIR" -name "*.db.gz" -mtime +14 -delete 2>/dev/null || true

# Show backup summary
echo ""
echo "=== Backup Summary ==="
ls -lh "$BACKUP_DIR"/*_$DATE* 2>/dev/null || echo "No backups created"
echo ""
echo "Total backup size: $(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1 || echo '0')"
echo "Done!"
