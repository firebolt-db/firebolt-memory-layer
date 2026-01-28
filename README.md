# Firebolt Memory Layer (FML)

An intelligent, persistent memory system for LLM agents using local Firebolt Core with HNSW vector search. Designed to give Cursor (and other MCP-compatible tools) long-term memory that persists across sessions.

## What This Does

- **Working Memory**: Session-scoped context that persists during a conversation
- **Long-Term Memory**: Vector-indexed persistent storage with semantic search
- **Auto-Classification**: Memories are automatically categorized (episodic, semantic, procedural, preference)
- **Semantic Recall**: Find relevant memories based on meaning, not just keywords
- **100% Local**: Runs entirely on your machine using Firebolt Core + Ollama (no cloud dependencies)

---

## Quick Start (Recommended)

For the fastest setup, use the bootstrap script after cloning:

```bash
# Clone the repository
git clone git@github.com:johnkennedy-cmyk/Firebolt-Memory-Layer.git
cd Firebolt-Memory-Layer

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

After bootstrap completes, **restart Cursor** and start chatting!

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
git clone git@github.com:johnkennedy-cmyk/Firebolt-Memory-Layer.git
cd Firebolt-Memory-Layer

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

### Step 8: Configure Cursor to Use FML

Create or edit `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "fml": {
      "command": "/path/to/Firebolt-Memory-Layer/fml/fml-server/.venv/bin/python",
      "args": ["-m", "src.server"],
      "cwd": "/path/to/Firebolt-Memory-Layer/fml/fml-server",
      "env": {
        "PYTHONPATH": "/path/to/Firebolt-Memory-Layer/fml/fml-server"
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
      "command": "/Users/YOUR_USERNAME/DevelopmentArea/Firebolt-Memory-Layer/fml/fml-server/.venv/bin/python",
      "args": ["-m", "src.server"],
      "cwd": "/Users/YOUR_USERNAME/DevelopmentArea/Firebolt-Memory-Layer/fml/fml-server",
      "env": {
        "PYTHONPATH": "/Users/YOUR_USERNAME/DevelopmentArea/Firebolt-Memory-Layer/fml/fml-server"
      }
    }
  }
}
```

### Step 9: Add Global Cursor Rules

Create `~/.cursor/rules/fml-memory.mdc` with the content from `cursor-rules/fml-memory.mdc` in this repo. This tells all Cursor agents to use FML automatically.

### Step 10: Restart Cursor

After adding the MCP config and rules, restart Cursor completely (Cmd+Q, then reopen).

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

### FML not responding in Cursor
1. Check Firebolt Core is running: `curl http://localhost:3473/?output_format=TabSeparated -d "SELECT 1"`
2. Check Ollama is running: `curl http://localhost:11434/api/tags`
3. Check MCP config path is correct in `~/.cursor/mcp.json`
4. Restart Cursor completely (Cmd+Q)

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

---

## Project Structure

```
Firebolt-Memory-Layer/
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
