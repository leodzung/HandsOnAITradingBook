#!/bin/bash
# Database Backup Script
# Run manually or via cron: 0 */6 * * * /path/to/backup_databases.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="$SCRIPT_DIR/data"
BACKUP_DIR="$SCRIPT_DIR/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p "$BACKUP_DIR"

echo "=== Database Backup: $DATE ==="

# Backup critical databases using SQLite's backup command (safe for active DBs)
for db in training_history.db price_tracking.db positions_price_level.db positions.db; do
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
        if [ "$SIZE" -gt 100000000 ]; then  # >100MB
            echo "  Compressing (${SIZE} bytes)..."
            gzip "$BACKUP_FILE"
            BACKUP_FILE="$BACKUP_FILE.gz"
        fi

        echo "  Created: $(basename $BACKUP_FILE)"
    fi
done

# Cleanup old backups (keep last 7 days)
echo "Cleaning up old backups..."
find "$BACKUP_DIR" -name "*.db" -mtime +7 -delete 2>/dev/null || true
find "$BACKUP_DIR" -name "*.db.gz" -mtime +7 -delete 2>/dev/null || true

# Show backup summary
echo ""
echo "=== Backup Summary ==="
ls -lh "$BACKUP_DIR"/*_$DATE* 2>/dev/null || echo "No backups created"
echo ""
echo "Total backup size: $(du -sh "$BACKUP_DIR" | cut -f1)"
echo "Done!"
