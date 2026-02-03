# Firebolt Memory Layer (FML)

An intelligent, persistent memory system for LLM agents using local Firebolt Core with HNSW vector search. Designed to give Cursor, Claude Code, Antigravity Codes, and other MCP-compatible tools long-term memory that persists across sessions. **Includes setup instructions for Antigravity Codes, Claude Code, Google Gemini, and Cursor IDE.**

## Credits

**Core Author:** [John Tuite](https://github.com/tuitejc-firebolt) - The FML MCP server architecture and implementation is John's work. This project builds upon his foundational design for intelligent memory management in LLM agents.

---

## What This Does

- **Working Memory**: Session-scoped context that persists during a conversation
- **Long-Term Memory**: Vector-indexed persistent storage with semantic search
- **Auto-Classification**: Memories are automatically categorized (episodic, semantic, procedural, preference)
- **Semantic Recall**: Find relevant memories based on meaning, not just keywords
- **100% Local**: Runs entirely on your machine using Firebolt Core + Ollama (no cloud dependencies)

---

## Quick Start (Recommended)

**Multi-Platform Support:** FML works with Cursor IDE, Claude Code, Antigravity Codes, Google Gemini, and any MCP-compatible client. See the [Platform Setup Guide](fml/fml-server/docs/MCP_PLATFORM_SETUP.md) for platform-specific instructions.

For the fastest setup, use the bootstrap script after cloning:

```bash
# Clone the repository
git clone git@github.com:firebolt-db/firebolt-memory-layer.git
cd firebolt-memory-layer

# Ensure Firebolt Core and Ollama are running first (see Prerequisites below)

# Run the bootstrap script - does everything automatically
cd fml/fml-server
./scripts/bootstrap.sh
```

The bootstrap script will:
- Set up Python virtual environment and dependencies
- Create database schema and tables
- **Seed core memories** (security rules, workflows, troubleshooting guides)
- Configure Cursor IDE with FML rules and MCP settings
- Set up pre-commit security hooks

After bootstrap completes, **restart your MCP client** (Cursor IDE: Cmd+Q, Claude Code: quit and reopen, Gemini CLI: restart) and start chatting!

---

## Manual Setup Guide

If you prefer manual setup or the bootstrap script doesn't work for your environment:

### Prerequisites

You need:
- **macOS** (tested on macOS 15.x)
- **Docker Desktop** installed and running
- **Python 3.10+** (3.14 recommended)
- **Homebrew** for package management
- **Cursor IDE** (or any MCP-compatible client)

### Step 1: Install Dependencies

```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python (if needed)
brew install python@3.14

# Install Ollama (local LLM)
brew install ollama

# Start Ollama and pull required models
ollama serve  # Run in a separate terminal, keep it running
ollama pull llama3:8b        # For classification
ollama pull nomic-embed-text  # For embeddings (768 dimensions)
```

### Step 2: Install Firebolt Core (Local Database)

Firebolt Core is a local version of Firebolt that runs in Docker.

```bash
# Install Firebolt Core using the official installer
bash <(curl -s https://get-core.firebolt.io/)

# Or if you have the manage script:
# cd firebolt-core-local && ./manage-firebolt.sh start

# Verify it's running (should return a response)
curl http://localhost:3473/?output_format=TabSeparated -d "SELECT 1"
```

Firebolt Core runs at `http://localhost:3473` by default.

### Step 3: Clone and Set Up FML

```bash
# Clone this repository
git clone git@github.com:firebolt-db/firebolt-memory-layer.git
cd firebolt-memory-layer

# Create Python virtual environment
cd fml/fml-server
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"
```

### Step 4: Configure Environment

```bash
# Copy example config
cp config/env.example .env

# Edit .env with your settings
nano .env
```

**For local-only setup (Firebolt Core + Ollama), use:**

```env
# Firebolt Core (Local)
FIREBOLT_USE_CORE=true
FIREBOLT_CORE_URL=http://localhost:3473
FIREBOLT_DATABASE=fml_memory

# Ollama (Local LLM - runs at localhost:11434)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3:8b
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
OLLAMA_EMBEDDING_DIMENSIONS=768

# Optional: OpenAI (only if you want to use OpenAI embeddings instead)
# OPENAI_API_KEY=your-key-here
```

### Step 5: Initialize Database Schema

```bash
# Ensure virtual environment is active
source .venv/bin/activate

# Create database and tables in Firebolt Core
python scripts/migrate.py
```

This creates:
- `fml_memory` database
- `session_contexts` table (working memory sessions)
- `working_memory_items` table (active context)
- `long_term_memories` table (persistent memories with vector index)
- `memory_access_log` table (analytics)
- `idx_memories_embedding` HNSW vector index (768 dimensions for Ollama)

### Step 6: Seed Core Memories (Recommended)

Pre-load essential memories for security rules, workflows, and troubleshooting:

```bash
# Seed core memories for optimal experience
python scripts/seed_core_memories.py
```

This creates foundational memories that help FML:
- Enforce security rules consistently
- Follow proper session workflows
- Troubleshoot common issues
- Understand FML architecture

### Step 7: Test the Setup

```bash
# Test all connections
python scripts/test_connections.py

# Test the MCP tools
python scripts/test_tools.py

# Test security validation
python scripts/test_security.py
```

### Step 8: Configure MCP Client to Use FML

FML works with any MCP-compatible client. See **[Platform Setup Guide](fml/fml-server/docs/MCP_PLATFORM_SETUP.md)** for detailed instructions for:
- **Claude Code** (Anthropic)
- **Google Gemini** / Antigravity Codes  
- **Cursor IDE** (shown below)

#### For Cursor IDE

Create or edit `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "fml": {
      "command": "/path/to/firebolt-memory-layer/fml/fml-server/.venv/bin/python",
      "args": ["-m", "src.server"],
      "cwd": "/path/to/firebolt-memory-layer/fml/fml-server",
      "env": {
        "PYTHONPATH": "/path/to/firebolt-memory-layer/fml/fml-server"
      }
    }
  }
}
```

**Important**: Replace `/path/to/` with the actual path where you cloned the repo.

Example for typical setup:
```json
{
  "mcpServers": {
    "fml": {
      "command": "/Users/YOUR_USERNAME/DevelopmentArea/firebolt-memory-layer/fml/fml-server/.venv/bin/python",
      "args": ["-m", "src.server"],
      "cwd": "/Users/YOUR_USERNAME/DevelopmentArea/firebolt-memory-layer/fml/fml-server",
      "env": {
        "PYTHONPATH": "/Users/YOUR_USERNAME/DevelopmentArea/firebolt-memory-layer/fml/fml-server"
      }
    }
  }
}
```

Configuration templates are available in `fml/fml-server/config/` directory.

### Step 9: Add Global Rules (Cursor IDE Only)

**Note:** This step is specific to Cursor IDE. Other MCP clients (Claude Code, Gemini CLI) don't use separate rule files.

For Cursor IDE: Create `~/.cursor/rules/fml-memory.mdc` with the content from `cursor-rules/fml-memory.mdc` in this repo. This tells all Cursor agents to use FML automatically.

### Step 10: Restart Your MCP Client

After adding the MCP config and rules, restart your MCP client completely:

- **Cursor IDE**: Quit completely (Cmd+Q on Mac, then reopen)
- **Claude Code**: Quit the application completely and reopen
- **Google Gemini CLI**: Restart the CLI (`gemini` command)
- **Other MCP clients**: Restart the application completely

---

## Verification

After setup, test in a new Cursor chat:

1. The agent should automatically call `init_session` at the start
2. The agent should call `recall_memories` based on your query
3. You can explicitly ask: "What do you remember about me?" to test recall

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Cursor IDE (MCP Client)                                    │
└─────────────────────┬───────────────────────────────────────┘
                      │ MCP Protocol (stdio)
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  FML MCP Server (Python)                                    │
│  ├── Working Memory Tools (5 tools)                         │
│  ├── Long-Term Memory Tools (5 tools)                       │
│  ├── Context Assembly Tools (2 tools)                       │
│  └── Stats/Analytics Tools (3 tools)                        │
└─────────────────────┬───────────────────────────────────────┘
                      │
          ┌──────────┴──────────┐
          ▼                     ▼
┌─────────────────┐   ┌─────────────────┐
│  Firebolt Core  │   │     Ollama      │
│  (localhost:    │   │  (localhost:    │
│   3473)         │   │   11434)        │
│  - SQL Storage  │   │  - Embeddings   │
│  - Vector Index │   │  - Classification│
└─────────────────┘   └─────────────────┘
```

---

## MCP Tools Available

### Working Memory (5 tools)
| Tool | Description |
|------|-------------|
| `init_session` | Initialize or resume a memory session |
| `add_to_working_memory` | Add item to working memory |
| `get_working_memory` | Retrieve current working memory state |
| `update_working_memory_item` | Update item properties (pinned, relevance) |
| `clear_working_memory` | Clear working memory for a session |

### Long-Term Memory (5 tools)
| Tool | Description |
|------|-------------|
| `store_memory` | Store a memory with auto-classification |
| `recall_memories` | Semantic search for relevant memories |
| `update_memory` | Update an existing memory |
| `forget_memory` | Delete a memory (soft delete) |
| `forget_all_user_memories` | GDPR-compliant full deletion |

### Context Assembly (2 tools)
| Tool | Description |
|------|-------------|
| `get_relevant_context` | Assemble optimal context from all sources |
| `checkpoint_working_memory` | Promote working memory to long-term |

### Stats (3 tools)
| Tool | Description |
|------|-------------|
| `get_fml_stats` | Server statistics and metrics |
| `get_recent_calls` | Recent API call history |
| `get_memory_analytics` | Memory distribution analytics |

---

## Memory Categories

Memories are auto-classified into human-aligned categories:

| Category | Use For | Subtypes |
|----------|---------|----------|
| `episodic` | Events, decisions, outcomes | decision, outcome, interaction, milestone |
| `semantic` | Facts, knowledge, entities | entity, concept, relationship, domain |
| `procedural` | Workflows, patterns, how-to | workflow, pattern, command, troubleshooting |
| `preference` | User preferences, style | coding_style, communication, tool_preference, constraint |

---

## Troubleshooting

### FML not responding in your MCP client
1. Check Firebolt Core is running: `curl http://localhost:3473/?output_format=TabSeparated -d "SELECT 1"`
2. Check Ollama is running: `curl http://localhost:11434/api/tags`
3. Check MCP config path is correct:
   - **Cursor IDE**: `~/.cursor/mcp.json`
   - **Claude Code**: `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)
   - **Google Gemini CLI**: `~/.gemini/settings.json`
4. Restart your MCP client completely:
   - **Cursor IDE**: Cmd+Q (Mac) or quit and reopen
   - **Claude Code**: Quit application completely and reopen
   - **Google Gemini CLI**: Restart the CLI

### Dashboard showing incorrect/stale data
The HTTP API server (used by the dashboard) doesn't auto-reload when code changes. If you see:
- Incorrect "All-Time Calls" counts (e.g., showing 4 instead of hundreds)
- Missing data in sections (Recent LLM Calls empty, Memory Data Size showing 0)
- Features not working that should be implemented

**Solution:** Check if the server needs a restart:
```bash
# Check server sync status
curl http://localhost:8082/api/version

# If "needs_restart": true, restart the server:
pkill -f "python.*http_api"
cd fml/fml-server
source .venv/bin/activate
PYTHONPATH=. python -m src.http_api &
```

The dashboard will also show a yellow warning banner when the server is running stale code, with the restart command included.

**Why this happens:** The `http_api` server is a separate Python process that loads code once at startup. Unlike the MCP server (which restarts with each MCP client session), the HTTP API runs continuously. After code changes, the running server still has the old code in memory until manually restarted.

### "tuple index out of range" error
This usually means the database is empty or the vector index doesn't exist. Run:
```bash
python scripts/migrate.py
```

### Vector dimension mismatch
Ensure you're using Ollama's `nomic-embed-text` (768 dimensions). If switching from OpenAI (1536 dimensions), you need to:
1. Drop the existing vector index
2. Recreate with `dimension = 768`
3. Re-embed all existing memories

### Transaction conflicts
Firebolt Core only allows one write transaction at a time. The FML server uses a mutex to serialize requests, but if you see transaction errors, wait a moment and retry.

---

## Dashboard (Optional)

FML includes a React dashboard for monitoring:

```bash
cd fml/dashboard
npm install
npm run dev
```

Also start the HTTP API:
```bash
cd fml/fml-server
source .venv/bin/activate
python -m src.http_api
```

Dashboard runs at `http://localhost:5174`

The dashboard visualizes both the FML memory flow and the optional Firebolt MCP query flow (see below).

---

## Running with Firebolt MCP (Optional)

For full Firebolt capabilities alongside memory management, you can run both FML and the official Firebolt MCP server in parallel. This gives your agent:

- **FML**: Persistent memory storage and semantic recall
- **Firebolt MCP**: Direct SQL queries against Firebolt Core databases

The dashboard UI shows both data flows side-by-side, demonstrating how they work together through Firebolt Core.

### Installing Firebolt MCP

The Firebolt MCP server is available via npm:

```bash
npm install -g @anthropic/firebolt-mcp
# Or use npx directly in the config
```

### Combined MCP Configuration

To run both servers, update your `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "fml": {
      "command": "/path/to/firebolt-memory-layer/fml/fml-server/.venv/bin/python",
      "args": ["-m", "src.server"],
      "cwd": "/path/to/firebolt-memory-layer/fml/fml-server",
      "env": {
        "PYTHONPATH": "/path/to/firebolt-memory-layer/fml/fml-server"
      }
    },
    "firebolt": {
      "command": "npx",
      "args": ["-y", "@anthropic/firebolt-mcp"],
      "env": {
        "FIREBOLT_CORE_URL": "http://localhost:3473"
      }
    }
  }
}
```

### How They Work Together

| Server | Purpose | Tools |
|--------|---------|-------|
| **FML** | Memory management | `store_memory`, `recall_memories`, `get_relevant_context`, etc. |
| **Firebolt MCP** | SQL queries | `firebolt_query`, `firebolt_connect`, `firebolt_docs_search` |

**Example workflow:**
1. Agent uses FML to recall relevant memories about a project
2. Agent uses Firebolt MCP to query actual data from your databases
3. Agent uses FML to store new learnings from the analysis

Both servers connect to the same Firebolt Core instance, so your memory data and query data live in the same database engine.

---

## Project Structure

```
firebolt-memory-layer/
├── fml/
│   ├── fml-server/              # Core MCP server (Python)
│   │   ├── src/
│   │   │   ├── server.py        # MCP server entry point
│   │   │   ├── config.py        # Configuration management
│   │   │   ├── db/              # Database client
│   │   │   ├── llm/             # Ollama/OpenAI integration
│   │   │   ├── memory/          # Memory taxonomy
│   │   │   └── tools/           # MCP tool implementations
│   │   ├── scripts/
│   │   │   ├── schema.sql       # Database schema
│   │   │   └── migrate.py       # Migration script
│   │   └── config/
│   │       └── env.example      # Example environment config
│   └── dashboard/               # React monitoring dashboard
├── cursor-rules/
│   └── fml-memory.mdc           # Global Cursor rules for FML
├── firebolt-core-local/         # Firebolt Core management (if present)
└── README.md                    # This file
```

---

## Security

FML implements multiple layers of security to protect sensitive data.

### Built-in Secret Detection

FML includes **programmatic security validation** that automatically blocks storage of sensitive data. When you attempt to store content containing secrets, the operation is rejected with a detailed error.

**Detected patterns include:**

| Category | Examples |
|----------|----------|
| **API Keys** | OpenAI (`sk-*`), GitHub (`ghp_*`), AWS (`AKIA*`), Google (`AIza*`), Anthropic, Slack, Stripe |
| **Tokens** | Bearer tokens, JWT tokens, Authorization headers |
| **Passwords** | Password assignments, database connection strings, passwords in URLs |
| **Private Keys** | RSA, PGP, and generic private key blocks |
| **Secrets** | Generic secret/token assignments, `.env`-style content |

**Example rejection:**
```json
{
  "error": "SECURITY_VIOLATION",
  "message": "SECURITY BLOCK: Content contains 1 critical security violation(s). Detected: OpenAI API Key.",
  "hint": "Sensitive data like API keys, passwords, and tokens should not be stored in memory."
}
```

### Security Best Practices

When using FML, follow these guidelines:

1. **Never store actual credentials** - Store descriptions or references instead
   - ❌ `"The API key is sk-abc123..."`
   - ✅ `"OpenAI API key is stored in .env as OPENAI_API_KEY"`

2. **Use environment variables** - All secrets should be in `.env` files
   - `.env` files are git-ignored by default
   - Use `.env.example` for templates with placeholder values

3. **Local-first architecture** - When using Firebolt Core + Ollama:
   - No data leaves your machine
   - No cloud API calls required
   - Full control over your data

### Pre-commit Hooks

The repository includes pre-commit hooks for additional security:

```bash
# Install pre-commit hooks
cd fml/fml-server
pip install pre-commit detect-secrets
pre-commit install

# Run security scan manually
pre-commit run --all-files

# Scan for secrets
detect-secrets scan .
```

**Configured hooks:**
- `detect-secrets` - Scans for hardcoded credentials
- `detect-private-key` - Prevents committing private keys
- `check-env-files` - Blocks `.env` file commits

### Running Security Tests

Verify the security validation is working:

```bash
cd fml/fml-server
source .venv/bin/activate
python scripts/test_security.py
```

### Reporting Security Issues

If you discover a security vulnerability, please:
1. **Do not** open a public issue
2. Email the maintainer directly with details
3. Allow time for a fix before public disclosure

---

## License

Apache 2.0
