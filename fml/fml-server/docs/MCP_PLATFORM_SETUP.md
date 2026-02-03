# FML MCP Server - Platform Setup Guide

This guide covers the requirements and configuration needed to enable FML (Firebolt Memory Layer) with different MCP-compatible platforms: Antigravity Codes, Google Gemini, and Claude Code.

## Overview

FML is an MCP (Model Context Protocol) server that provides intelligent memory management for LLMs. It uses **stdio transport** (standard input/output) which is compatible with all major MCP clients.

## Prerequisites

Before configuring FML for any platform, ensure:

1. ✅ **FML Server is installed and working**
   ```bash
   cd fml/fml-server
   source .venv/bin/activate
   python -m src.server  # Should start without errors
   ```

2. ✅ **Firebolt Core is running** (for local setup)
   ```bash
   curl http://localhost:3473/?output_format=TabSeparated -d "SELECT 1"
   ```

3. ✅ **Ollama is running** (for local embeddings/classification)
   ```bash
   curl http://localhost:11434/api/tags
   ```

4. ✅ **Environment variables are configured** (`.env` file in `fml-server/`)
   - See `config/env.example` for required variables

---

## Platform-Specific Configuration

### 1. Claude Code (Anthropic)

Claude Code supports MCP servers via configuration files. FML uses **stdio transport**, which Claude Code fully supports.

#### Configuration Location

**macOS:**
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Windows:**
```
%APPDATA%\Claude\claude_desktop_config.json
```

**Linux:**
```
~/.config/Claude/claude_desktop_config.json
```

#### MCP Configuration

Add FML to your Claude Code configuration:

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

**Important:** Replace `/FULL/PATH/TO/` with your actual path.

**Example for macOS:**
```json
{
  "mcpServers": {
    "fml": {
      "command": "/Users/johnkennedy/DevelopmentArea/Firebolt-Memory-Layer/fml/fml-server/.venv/bin/python",
      "args": ["-m", "src.server"],
      "cwd": "/Users/johnkennedy/DevelopmentArea/Firebolt-Memory-Layer/fml/fml-server",
      "env": {
        "PYTHONPATH": "/Users/johnkennedy/DevelopmentArea/Firebolt-Memory-Layer/fml/fml-server"
      }
    }
  }
}
```

#### Restart Instructions

After configuring FML, you must restart Claude Code completely for the changes to take effect:

- **macOS**: Quit Claude Code (Cmd+Q) and reopen
- **Windows**: Close Claude Code completely and reopen
- **Linux**: Quit Claude Code completely and reopen

**Note:** There is no reload command - a full application restart is required.

#### Verification

1. Restart Claude Code completely (quit and reopen)
2. Open a new conversation
3. Ask Claude: "What memory tools are available?"
4. Claude should be able to call FML tools like `init_session`, `recall_memories`, etc.

#### Additional Notes

- Claude Code supports **stdio**, **SSE**, and **HTTP** transports
- FML uses stdio (most compatible)
- No additional authentication required for local servers
- Environment variables from `.env` are automatically loaded by the server

---

### 2. Google Gemini (via Antigravity or Direct)

Google Gemini can access MCP servers through Antigravity Codes or direct configuration.

#### Option A: Via Antigravity Codes Directory

**Antigravity Codes** (https://antigravity.codes) is a directory of MCP servers. To make FML available:

1. **Create an Antigravity-compatible package.json** (if publishing to npm):

   ```json
   {
     "name": "@your-org/fml-mcp",
     "version": "1.0.0",
     "description": "Firebolt Memory Layer - Intelligent memory management for LLMs",
     "main": "index.js",
     "bin": {
       "fml-mcp": "./bin/fml-mcp.js"
     },
     "scripts": {
       "start": "python -m src.server"
     },
     "keywords": ["mcp", "memory", "firebolt", "llm"],
     "author": "Your Name",
     "license": "Apache-2.0"
   }
   ```

2. **Or use direct path configuration** (recommended for local development):

   Gemini/Google AI Studio MCP configuration location (if supported):
   ```
   ~/.config/google-ai/mcp.json
   ```

   Configuration format:
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

#### Option B: Direct Integration (if Google provides MCP support)

If Google AI Studio or Gemini directly supports MCP:

1. Check Google's MCP documentation for configuration file location
2. Use the same stdio configuration as Claude Code
3. Ensure Python path is absolute and accessible

#### Restart Instructions

After configuring FML, you must restart the Gemini CLI for the changes to take effect:

- **Gemini CLI**: Exit the CLI (Ctrl+C or `exit`) and restart with `gemini` command
- **Google AI Studio**: If using web interface, refresh the page or restart the session

**Note:** There is no reload command - a full restart is required. Configuration changes in `settings.json` are only picked up on startup.

#### Verification

- Restart the Gemini CLI (exit and restart)
- Test MCP connection using Google's MCP test tools (if available)
- Verify FML tools appear in Gemini's available tools list
- Test basic operations: `init_session`, `recall_memories`

---

### 3. Antigravity Codes (Publishing/Registration)

**Antigravity Codes** (https://antigravity.codes) is a directory that helps developers discover MCP servers. To make FML discoverable:

#### Requirements for Antigravity Listing

1. **GitHub Repository** (public or private)
   - Well-documented README.md
   - Clear setup instructions
   - Example configurations

2. **npm Package** (optional but recommended)
   - Allows installation via `npx -y @your-org/fml-mcp`
   - Makes it easier for users to try FML

3. **MCP Server Metadata**
   - Server name: `firebolt-memory-layer` or `fml`
   - Transport: `stdio`
   - Language: `python`
   - Tools: List of available tools (see below)

#### FML Server Metadata

```json
{
  "name": "firebolt-memory-layer",
  "displayName": "Firebolt Memory Layer (FML)",
  "description": "Intelligent memory management for LLMs using Firebolt Core with HNSW vector search",
  "version": "1.0.0",
  "transport": "stdio",
  "language": "python",
  "repository": "https://github.com/firebolt-db/firebolt-memory-layer",
  "tools": [
    {
      "name": "init_session",
      "description": "Initialize or resume a memory session"
    },
    {
      "name": "add_to_working_memory",
      "description": "Add item to current session's working memory"
    },
    {
      "name": "get_working_memory",
      "description": "Retrieve current working memory state"
    },
    {
      "name": "store_memory",
      "description": "Store content in long-term memory with auto-classification"
    },
    {
      "name": "recall_memories",
      "description": "Search long-term memory with semantic similarity"
    },
    {
      "name": "get_relevant_context",
      "description": "Smart context assembly from all memory sources"
    },
    {
      "name": "checkpoint_working_memory",
      "description": "Promote working memory to long-term storage"
    },
    {
      "name": "get_fml_stats",
      "description": "Get server statistics and metrics"
    }
  ],
  "requirements": {
    "python": ">=3.10",
    "dependencies": [
      "firebolt-sdk>=1.0.0",
      "mcp>=0.1.0",
      "ollama>=0.1.0"
    ]
  },
  "setup": {
    "steps": [
      "Install Firebolt Core (local) or configure Firebolt Cloud",
      "Install Ollama for local LLM",
      "Configure .env file with database credentials",
      "Run database migrations",
      "Add MCP server to client configuration"
    ]
  }
}
```

#### Publishing to Antigravity

1. **Create a Pull Request** to Antigravity's MCP directory (if they accept contributions)
2. **Or submit via their form** (check antigravity.codes for submission process)
3. **Include:**
   - Repository URL
   - MCP configuration example
   - Quick start guide
   - Tool descriptions

#### Antigravity-Compatible Installation

If published to npm, users could install via:

```json
{
  "mcpServers": {
    "fml": {
      "command": "npx",
      "args": ["-y", "@firebolt/fml-mcp"]
    }
  }
}
```

**Note:** This requires creating a wrapper npm package that handles Python environment setup.

---

## Common Configuration Requirements

### Environment Variables

All platforms require the same environment setup. The FML server reads from `.env` file:

```env
# Firebolt Core (Local - Recommended)
FIREBOLT_USE_CORE=true
FIREBOLT_CORE_URL=http://localhost:3473
FIREBOLT_DATABASE=fml_memory

# Ollama (Local LLM)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3:8b
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
OLLAMA_EMBEDDING_DIMENSIONS=768

# Optional: OpenAI (if not using Ollama)
# OPENAI_API_KEY=your-key-here
```

### Path Requirements

- **Absolute paths required** - MCP clients need full paths to Python executable
- **Virtual environment** - Use `.venv/bin/python` from the project directory
- **PYTHONPATH** - Must include the `fml-server` directory

### Transport Protocol

FML uses **stdio transport** (standard input/output), which is:
- ✅ Supported by all major MCP clients
- ✅ No network configuration needed
- ✅ Works with local servers
- ✅ Secure (no exposed ports)

---

## Platform-Specific Guidance

### Claude Code

**Strengths:**
- Excellent MCP support
- Clear documentation
- Active development

**Considerations:**
- Configuration file location varies by OS
- Requires full restart after config changes
- Supports stdio, SSE, and HTTP transports

**Best Practices:**
- Use absolute paths
- Test with simple tool calls first
- Check Claude's MCP logs if issues occur

### Google Gemini / Antigravity

**Strengths:**
- Growing MCP ecosystem
- Antigravity provides discovery mechanism
- Can work with multiple AI platforms

**Considerations:**
- MCP support may vary by Google product
- Antigravity requires npm package for easy installation
- May need wrapper scripts for Python servers

**Best Practices:**
- Create npm wrapper if publishing to Antigravity
- Document setup clearly for non-technical users
- Provide Docker option for easier deployment

### General MCP Client Requirements

All MCP clients should support:

1. **stdio transport** - FML's primary transport
2. **Environment variable passing** - Via `env` field in config
3. **Working directory** - Via `cwd` field in config
4. **Command arguments** - Via `args` field in config

---

## Troubleshooting

### Issue: MCP Server Not Starting

**Symptoms:** Client can't connect to FML

**Solutions:**
1. Verify Python path is correct and executable
2. Check virtual environment is activated
3. Test server manually: `python -m src.server`
4. Verify `.env` file exists and has correct values
5. Check Firebolt Core and Ollama are running
6. **Restart your MCP client** (see restart commands below)

### Issue: Tools Not Available

**Symptoms:** Client connects but tools don't appear

**Solutions:**
1. Check server logs for registration errors
2. Verify all dependencies are installed
3. Test tools directly: `python scripts/test_tools.py`
4. Check MCP client supports the tool schema version

### Issue: Authentication Errors

**Symptoms:** Database connection failures

**Solutions:**
1. Verify Firebolt Core is accessible at configured URL
2. Check database exists: `python scripts/migrate.py`
3. Verify Ollama is running if using local embeddings
4. Check `.env` file has correct credentials

### Issue: Platform-Specific Errors

**Claude Code:**
- Check config file location matches your OS
- Verify JSON syntax is valid
- **Restart Claude Code completely** (quit application and reopen - no reload command available)

**Google/Gemini CLI:**
- Verify MCP support is enabled (if available)
- Check configuration file location (`~/.gemini/settings.json`)
- **Restart Gemini CLI** (exit with Ctrl+C or `exit`, then restart with `gemini` command)
- Test with simple MCP server first

**Cursor IDE:**
- Check config file location (`~/.cursor/mcp.json`)
- Verify JSON syntax is valid
- **Restart Cursor completely** (Cmd+Q on Mac, then reopen)

**Antigravity:**
- Antigravity is a directory, not a client - follow instructions for your specific client
- Verify npm package structure (if published)
- Check wrapper script handles Python correctly
- Test installation on clean environment

---

## Restart Commands Reference

After making MCP configuration changes, you must restart your MCP client:

| Platform | Restart Command | Notes |
|----------|----------------|-------|
| **Cursor IDE** (macOS) | `Cmd+Q` then reopen | Full application quit required |
| **Cursor IDE** (Windows/Linux) | Quit application, then reopen | Full application quit required |
| **Claude Code** (macOS) | `Cmd+Q` then reopen | Full application quit required - no reload command |
| **Claude Code** (Windows) | Close application, then reopen | Full application quit required |
| **Claude Code** (Linux) | Quit application, then reopen | Full application quit required |
| **Google Gemini CLI** | `exit` then `gemini` | Exit CLI and restart - no reload command |
| **Google AI Studio** (Web) | Refresh page or restart session | Browser refresh may be sufficient |

**Important:** Most MCP clients do not support hot-reloading of configuration. A full restart is required for changes to take effect.

---

## Testing MCP Configuration

### Manual Test

Test FML server directly:

```bash
cd fml/fml-server
source .venv/bin/activate
python -m src.server
```

Should start without errors and wait for stdio input.

### MCP Client Test

Use an MCP testing tool or the client's built-in test:

1. **Claude Code:** Check MCP status in settings
2. **Custom test:** Use MCP inspector tools
3. **Logs:** Check client logs for connection errors

### Tool Availability Test

Once connected, verify tools are available:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}
```

Should return list including `init_session`, `recall_memories`, etc.

---

## Next Steps

1. ✅ **Configure for your platform** using the examples above
2. ✅ **Test basic connectivity** with `init_session` tool
3. ✅ **Verify memory operations** with `store_memory` and `recall_memories`
4. ✅ **Check platform-specific documentation** for any additional requirements
5. ✅ **Consider publishing to Antigravity** if you want broader discoverability

---

## Additional Resources

- **FML Documentation:** See `README.md` in project root
- **MCP Specification:** https://modelcontextprotocol.io
- **Antigravity Codes:** https://antigravity.codes
- **Claude Code MCP Docs:** https://docs.claude.com/en/docs/claude-code/mcp
- **Firebolt Core:** https://docs.firebolt.io

---

## Summary

| Platform | Config Location | Transport | Status |
|----------|----------------|-----------|--------|
| **Claude Code** | `~/Library/Application Support/Claude/claude_desktop_config.json` | stdio | ✅ Fully Supported |
| **Google Gemini** | Platform-specific (check docs) | stdio | ⚠️ Verify Support |
| **Antigravity** | Via npm package or direct config | stdio | ✅ Via Directory |

**Key Requirements:**
- ✅ Absolute Python path
- ✅ Virtual environment activated
- ✅ Firebolt Core running (local setup)
- ✅ Ollama running (local setup)
- ✅ `.env` file configured
- ✅ Database migrated

All platforms use the same MCP configuration format - only the config file location differs.
