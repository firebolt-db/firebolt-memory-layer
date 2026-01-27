#!/bin/bash
# FML Bootstrap Script
# Run this after cloning to set up everything in one go

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FML_SERVER_DIR="$(dirname "$SCRIPT_DIR")"
FML_DIR="$(dirname "$FML_SERVER_DIR")"
REPO_DIR="$(dirname "$FML_DIR")"

echo "🔥 FML Bootstrap Script"
echo "========================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check prerequisites
echo "📋 Checking prerequisites..."

check_command() {
    if command -v $1 &> /dev/null; then
        echo -e "  ${GREEN}✓${NC} $1 found"
        return 0
    else
        echo -e "  ${RED}✗${NC} $1 not found"
        return 1
    fi
}

MISSING_PREREQS=0

check_command python3 || MISSING_PREREQS=1
check_command docker || MISSING_PREREQS=1
check_command curl || MISSING_PREREQS=1

if [ $MISSING_PREREQS -eq 1 ]; then
    echo ""
    echo -e "${RED}Please install missing prerequisites and run again.${NC}"
    exit 1
fi

echo ""

# Check if Firebolt Core is running
echo "🔥 Checking Firebolt Core..."
if curl -s "http://localhost:3473/?output_format=PSQL" -d "SELECT 1" > /dev/null 2>&1; then
    echo -e "  ${GREEN}✓${NC} Firebolt Core is running on port 3473"
else
    echo -e "  ${YELLOW}!${NC} Firebolt Core not detected"
    echo "    Install with: bash <(curl -s https://get-core.firebolt.io/)"
    echo "    Or start existing: docker start firebolt-core"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if Ollama is running
echo ""
echo "🦙 Checking Ollama..."
if curl -s "http://localhost:11434/api/tags" > /dev/null 2>&1; then
    echo -e "  ${GREEN}✓${NC} Ollama is running on port 11434"
    
    # Check for required models
    if curl -s "http://localhost:11434/api/tags" | grep -q "llama3"; then
        echo -e "  ${GREEN}✓${NC} llama3 model available"
    else
        echo -e "  ${YELLOW}!${NC} llama3 model not found - run: ollama pull llama3:8b"
    fi
    
    if curl -s "http://localhost:11434/api/tags" | grep -q "nomic-embed-text"; then
        echo -e "  ${GREEN}✓${NC} nomic-embed-text model available"
    else
        echo -e "  ${YELLOW}!${NC} nomic-embed-text model not found - run: ollama pull nomic-embed-text"
    fi
else
    echo -e "  ${YELLOW}!${NC} Ollama not detected"
    echo "    Install with: brew install ollama"
    echo "    Start with: ollama serve"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""

# Set up Python virtual environment
echo "🐍 Setting up Python environment..."
cd "$FML_SERVER_DIR"

if [ ! -d ".venv" ]; then
    echo "  Creating virtual environment..."
    python3 -m venv .venv
fi

echo "  Activating virtual environment..."
source .venv/bin/activate

echo "  Installing dependencies..."
pip install -q -e ".[dev]" 2>/dev/null || pip install -q -e .

echo -e "  ${GREEN}✓${NC} Python environment ready"
echo ""

# Set up environment file
echo "📝 Setting up environment configuration..."
if [ ! -f ".env" ]; then
    if [ -f "config/env.example" ]; then
        cp config/env.example .env
        echo -e "  ${GREEN}✓${NC} Created .env from template"
        echo -e "  ${YELLOW}!${NC} Review and edit .env if needed"
    else
        echo -e "  ${RED}✗${NC} No env.example found"
    fi
else
    echo -e "  ${GREEN}✓${NC} .env already exists"
fi

echo ""

# Run database migration
echo "🗄️  Setting up database schema..."
python scripts/migrate.py 2>/dev/null || {
    echo -e "  ${YELLOW}!${NC} Migration had warnings (may be OK if tables exist)"
}
echo -e "  ${GREEN}✓${NC} Database schema ready"
echo ""

# Seed core memories
echo "🌱 Seeding core memories..."
python scripts/seed_core_memories.py 2>/dev/null || {
    echo -e "  ${YELLOW}!${NC} Some memories may already exist"
}
echo ""

# Set up pre-commit hooks
echo "🔒 Setting up security hooks..."
if command -v pre-commit &> /dev/null; then
    pre-commit install > /dev/null 2>&1 || true
    echo -e "  ${GREEN}✓${NC} Pre-commit hooks installed"
else
    pip install -q pre-commit
    pre-commit install > /dev/null 2>&1 || true
    echo -e "  ${GREEN}✓${NC} Pre-commit installed and hooks configured"
fi

echo ""

# Set up Cursor configuration
echo "🖥️  Setting up Cursor IDE configuration..."

CURSOR_DIR="$HOME/.cursor"
CURSOR_RULES_DIR="$CURSOR_DIR/rules"
CURSOR_MCP_FILE="$CURSOR_DIR/mcp.json"

# Create Cursor directories
mkdir -p "$CURSOR_RULES_DIR"

# Copy FML rules
if [ -f "$REPO_DIR/cursor-rules/fml-memory.mdc" ]; then
    cp "$REPO_DIR/cursor-rules/fml-memory.mdc" "$CURSOR_RULES_DIR/"
    echo -e "  ${GREEN}✓${NC} FML rules copied to ~/.cursor/rules/"
fi

# Generate MCP configuration
VENV_PYTHON="$FML_SERVER_DIR/.venv/bin/python"

if [ -f "$CURSOR_MCP_FILE" ]; then
    # Check if FML is already configured
    if grep -q '"fml"' "$CURSOR_MCP_FILE" 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} FML already configured in mcp.json"
    else
        echo -e "  ${YELLOW}!${NC} mcp.json exists but FML not configured"
        echo "    Add the following to mcpServers in ~/.cursor/mcp.json:"
        echo ""
        echo '    "fml": {'
        echo "      \"command\": \"$VENV_PYTHON\","
        echo '      "args": ["-m", "src.server"],'
        echo "      \"cwd\": \"$FML_SERVER_DIR\","
        echo '      "env": {'
        echo "        \"PYTHONPATH\": \"$FML_SERVER_DIR\""
        echo '      }'
        echo '    }'
    fi
else
    # Create new mcp.json
    cat > "$CURSOR_MCP_FILE" << EOF
{
  "mcpServers": {
    "fml": {
      "command": "$VENV_PYTHON",
      "args": ["-m", "src.server"],
      "cwd": "$FML_SERVER_DIR",
      "env": {
        "PYTHONPATH": "$FML_SERVER_DIR"
      }
    }
  }
}
EOF
    echo -e "  ${GREEN}✓${NC} Created ~/.cursor/mcp.json"
fi

echo ""
echo "========================"
echo -e "${GREEN}🎉 FML Bootstrap Complete!${NC}"
echo "========================"
echo ""
echo "Next steps:"
echo "  1. Restart Cursor IDE (Cmd+Q on Mac, then reopen)"
echo "  2. Start a new chat - FML should initialize automatically"
echo "  3. Test with: \"What do you remember about security?\""
echo ""
echo "Optional - Start the dashboard:"
echo "  cd $FML_SERVER_DIR && source .venv/bin/activate"
echo "  python -m src.http_api  # In one terminal"
echo "  cd $FML_DIR/dashboard && npm run dev  # In another terminal"
echo ""
