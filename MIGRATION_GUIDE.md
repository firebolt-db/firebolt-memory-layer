# FML Migration Guide

## Quick Migration to New Laptop

### What's Already Safe ✅
- **Code**: Stored in GitHub at `github.com/johnkennedy-cmyk/Firebolt-Memory-Layer`
- **Memories**: Stored in Firebolt database (persists independently)

---

## Step 1: Backup Secrets to Google Drive

Copy these files to a **private** Google Drive folder (e.g., `FML-Secrets/`):

```bash
# On OLD laptop - copy these to Google Drive:
cp fml/fml-server/.env  → Google Drive/FML-Secrets/env-backup.txt
cp ~/.cursor/mcp.json   → Google Drive/FML-Secrets/mcp-backup.json
```

⚠️ **Security**: These contain API keys - keep the Google Drive folder private!

---

## Step 2: Setup New Laptop

### 2.1 Install Prerequisites

```bash
# Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Core tools
brew install python@3.11 node git

# Ollama for local LLM
brew install ollama
```

### 2.2 Clone the Repository

```bash
cd ~/DevelopmentArea  # or your preferred location
git clone https://github.com/johnkennedy-cmyk/Firebolt-Memory-Layer.git
cd Firebolt-Memory-Layer
```

### 2.3 Restore Secrets from Google Drive

```bash
# Copy from Google Drive back to correct locations:
cp "Google Drive/FML-Secrets/env-backup.txt" fml/fml-server/.env
cp "Google Drive/FML-Secrets/mcp-backup.json" ~/.cursor/mcp.json
```

### 2.4 Update Paths in mcp.json

Edit `~/.cursor/mcp.json` to match your new laptop's paths:

```json
{
  "mcpServers": {
    "firebolt": {
      "url": "http://localhost:8080/sse"
    },
    "fml": {
      "command": "/PATH/TO/Firebolt-Memory-Layer/fml/fml-server/.venv/bin/python",
      "args": ["-m", "src.server"],
      "cwd": "/PATH/TO/Firebolt-Memory-Layer/fml/fml-server",
      "env": {
        "PYTHONPATH": "/PATH/TO/Firebolt-Memory-Layer/fml/fml-server"
      }
    }
  }
}
```

### 2.5 Setup Python Environment

```bash
cd fml/fml-server

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"
```

### 2.6 Setup Dashboard

```bash
cd ../dashboard
npm install
```

### 2.7 Pull Ollama Models

```bash
# Start Ollama service
ollama serve &

# Pull required models
ollama pull nomic-embed-text
ollama pull mistral:7b
```

### 2.8 (Optional) Install Firebolt Local Core

If using local Firebolt Core instead of cloud:

```bash
# Download from Firebolt
# Follow instructions at: https://docs.firebolt.io/local-core
```

---

## Step 3: Verify Installation

```bash
# Test connections
cd fml/fml-server
source .venv/bin/activate
python scripts/test_connections.py

# Start the dashboard
cd ../dashboard
npm run dev
```

Open http://localhost:5174 - you should see your existing memories!

---

## Files Summary

| What | Where | Backup Method |
|------|-------|---------------|
| Source code | GitHub | `git push` |
| Secrets (.env) | Google Drive (encrypted) | Manual copy |
| Cursor config | Google Drive | Manual copy |
| Memories | Firebolt DB | Automatic (cloud-persisted) |
| Ollama models | Local | Re-download with `ollama pull` |

---

## Troubleshooting

### "MCP server not connecting"
- Check paths in `~/.cursor/mcp.json` match your new laptop
- Ensure `.venv` is created and activated

### "Ollama connection failed"  
- Run `ollama serve` in a terminal
- Verify with `curl http://localhost:11434/api/tags`

### "Firebolt connection failed"
- Check `.env` has correct credentials
- For Local Core: ensure it's running on port 3473

---

## Security Reminders

1. **Never commit `.env`** - it's in `.gitignore` for a reason
2. **Keep Google Drive backup private** - contains API keys
3. **Rotate keys periodically** - especially after migration
