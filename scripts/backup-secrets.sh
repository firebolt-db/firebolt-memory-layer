#!/bin/bash
# FML Secrets Backup Script
# Creates a timestamped backup of sensitive configuration files

set -e

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$HOME/Desktop/FML-Backup-$TIMESTAMP"
PROJECT_DIR="$(dirname "$0")/.."

echo "🔐 FML Secrets Backup"
echo "===================="
echo ""

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup .env file
if [ -f "$PROJECT_DIR/fml/fml-server/.env" ]; then
    cp "$PROJECT_DIR/fml/fml-server/.env" "$BACKUP_DIR/fml-server.env"
    echo "✅ Backed up: fml-server/.env"
else
    echo "⚠️  Not found: fml-server/.env"
fi

# Backup Cursor MCP config
if [ -f "$HOME/.cursor/mcp.json" ]; then
    cp "$HOME/.cursor/mcp.json" "$BACKUP_DIR/cursor-mcp.json"
    echo "✅ Backed up: ~/.cursor/mcp.json"
else
    echo "⚠️  Not found: ~/.cursor/mcp.json"
fi

# Create a README in the backup
cat > "$BACKUP_DIR/README.txt" << 'EOF'
FML Configuration Backup
========================

This backup contains sensitive configuration files for the 
Firebolt Memory Layer (FML) project.

Files included:
- fml-server.env    → Restore to: fml/fml-server/.env
- cursor-mcp.json   → Restore to: ~/.cursor/mcp.json

⚠️  SECURITY WARNING:
These files contain API keys and credentials.
Keep this backup private and secure.

To restore on a new machine:
1. Clone the repo from GitHub
2. Copy fml-server.env to fml/fml-server/.env
3. Copy cursor-mcp.json to ~/.cursor/mcp.json
4. Update paths in mcp.json for new machine location
5. See MIGRATION_GUIDE.md for full instructions
EOF

echo ""
echo "📁 Backup created at: $BACKUP_DIR"
echo ""
echo "Next steps:"
echo "1. Open Finder: open \"$BACKUP_DIR\""
echo "2. Upload folder to Google Drive"
echo "3. Right-click → Share → Restricted (Only you)"
echo ""

# Open the folder in Finder
open "$BACKUP_DIR"
