#!/bin/bash
# FML Daily Maintenance Cron Script
# Runs Monday-Friday to backup and maintain memory quality
#
# Install with:
#   crontab -e
#   0 9 * * 1-5 /path/to/Firebolt-Memory-Layer/fml/fml-server/scripts/cron_maintenance.sh
#
# This runs at 9:00 AM Monday-Friday

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_PATH="$PROJECT_DIR/.venv"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/maintenance_$(date +%Y%m%d).log"

# Default user - change this or pass as argument
USER_ID="${1:-johnkennedy}"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=========================================="
log "FML Daily Maintenance Starting"
log "User: $USER_ID"
log "=========================================="

# Activate virtual environment
if [ -f "$VENV_PATH/bin/activate" ]; then
    source "$VENV_PATH/bin/activate"
    log "✓ Virtual environment activated"
else
    log "✗ Virtual environment not found at $VENV_PATH"
    exit 1
fi

# Change to project directory
cd "$PROJECT_DIR"

# Task 1: Daily Backup
log ""
log "--- Task 1: Daily Backup ---"
python scripts/daily_backup.py 2>&1 | tee -a "$LOG_FILE"

# Task 2: Memory Quality Report
log ""
log "--- Task 2: Quality Report ---"
python scripts/memory_quality.py "$USER_ID" report 2>&1 | tee -a "$LOG_FILE"

# Task 3: Apply Decay (gentle - 98% retention)
log ""
log "--- Task 3: Apply Decay ---"
python -c "
import sys
sys.path.insert(0, '.')
from scripts.memory_quality import apply_decay
apply_decay('$USER_ID', decay_rate=0.98)
" 2>&1 | tee -a "$LOG_FILE"

log ""
log "=========================================="
log "FML Daily Maintenance Complete"
log "=========================================="

# Cleanup old logs (keep 30 days)
find "$LOG_DIR" -name "maintenance_*.log" -mtime +30 -delete 2>/dev/null || true

exit 0
