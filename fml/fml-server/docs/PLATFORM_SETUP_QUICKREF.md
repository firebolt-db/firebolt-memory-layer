# FML Platform Setup - Quick Reference

## Summary

FML (Firebolt Memory Layer) is an MCP server that works with **any MCP-compatible client** using **stdio transport**. The configuration format is identical across platforms - only the config file location differs.

## Key Requirements

| Requirement | Details |
|-------------|---------|
| **Transport** | stdio (standard input/output) |
| **Python** | 3.10+ with virtual environment |
| **Dependencies** | Firebolt Core + Ollama (local setup) |
| **Config Format** | JSON with `command`, `args`, `cwd`, `env` |

## Platform Configuration Files

| Platform | Config File Location |
|----------|---------------------|
| **Cursor IDE** | `~/.cursor/mcp.json` |
| **Claude Code** (macOS) | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| **Claude Code** (Windows) | `%APPDATA%\Claude\claude_desktop_config.json` |
| **Claude Code** (Linux) | `~/.config/Claude/claude_desktop_config.json` |
| **Google Gemini** | Platform-specific (check Google docs) |

## Standard Configuration Template

```json
{
  "mcpServers": {
    "fml": {
      "command": "/FULL/PATH/TO/Firebolt-Memory-Layer/fml/fml-server/.venv/bin/python",
      "args": ["-m", "src.server"],
      "cwd": "/FULL/PATH/TO/Firebolt-Memory-Layer/fml/fml-server",
      "env": {
        "PYTHONPATH": "/FULL/PATH/TO/Firebolt-Memory-Layer/fml/fml-server"
      }
    }
  }
}
```

**Replace `/FULL/PATH/TO/` with your actual path.**

## Prerequisites Checklist

- [ ] FML server installed (`pip install -e ".[dev]"`)
- [ ] Firebolt Core running (`curl http://localhost:3473`)
- [ ] Ollama running (`curl http://localhost:11434/api/tags`)
- [ ] `.env` file configured (see `config/env.example`)
- [ ] Database migrated (`python scripts/migrate.py`)
- [ ] **Dashboard setup** (recommended for heavy usage - see below)

## Antigravity Codes

To make FML discoverable via Antigravity Codes:

1. **Option A:** Publish npm package (requires wrapper)
2. **Option B:** Direct configuration (same as above)
3. **Option C:** Submit to Antigravity directory

See [MCP_PLATFORM_SETUP.md](MCP_PLATFORM_SETUP.md) for full details.

## Restart Commands

After configuration, restart your MCP client:

| Platform | Restart Command |
|----------|----------------|
| **Cursor IDE** (macOS) | `Cmd+Q` then reopen |
| **Cursor IDE** (Windows/Linux) | Quit application, then reopen |
| **Claude Code** (all platforms) | Quit application completely, then reopen |
| **Google Gemini CLI** | `exit` then `gemini` |

**Note:** Most MCP clients require a full restart - no reload command available.

## Monitoring Dashboard (Recommended)

FML includes a **local monitoring dashboard** - critical for ongoing heavy usage. It provides real-time monitoring, troubleshooting, and analytics.

**Quick Start:**
```bash
# Terminal 1: HTTP API
cd fml/fml-server && source .venv/bin/activate && python -m src.http_api

# Terminal 2: Dashboard UI  
cd fml/dashboard && npm install && npm run dev
```

Access at `http://localhost:5174` - essential for production use and troubleshooting.

## Verification

After restarting your MCP client:

1. Test connection: `init_session` tool should be available
2. Test memory: `store_memory` and `recall_memories` should work
3. Verify tools appear in your client's tool list
4. **Monitor via dashboard** (if running) to track performance and troubleshoot issues

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Server won't start | Check Python path, verify venv activated |
| Tools not available | Check server logs, verify dependencies installed |
| Connection errors | Verify Firebolt Core and Ollama are running |

## Full Documentation

See **[MCP_PLATFORM_SETUP.md](MCP_PLATFORM_SETUP.md)** for:
- Detailed platform-specific instructions
- Antigravity publishing guide
- Troubleshooting steps
- Testing procedures
