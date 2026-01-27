#!/usr/bin/env python3
"""Seed core memories for FML.

This script pre-loads essential memories that every FML instance should have,
including security rules, best practices, and project knowledge.

Run after migrate.py to seed the initial memories:
    python scripts/seed_core_memories.py
"""

import sys
import os
import uuid
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.client import db
from src.llm.embeddings import embedding_service


# Core memories to seed - these are essential knowledge for FML operation
CORE_MEMORIES = [
    {
        "memory_category": "procedural",
        "memory_subtype": "workflow",
        "importance": 1.0,
        "content": """FML Security Rules - NEVER VIOLATE:

1. NEVER store actual credentials in memory:
   - API keys (sk-*, ghp_*, AKIA*, AIza*, xox*)
   - Passwords or secrets
   - Bearer tokens or JWTs
   - Private keys (RSA, PGP, SSH)
   - Database connection strings with credentials

2. ALWAYS store references instead of values:
   - BAD: "The API key is sk-abc123..."
   - GOOD: "OpenAI API key is stored in .env as OPENAI_API_KEY"

3. Security validation is enforced programmatically:
   - FML will reject attempts to store detected secrets
   - 20+ patterns are checked including API keys, tokens, passwords
   - Both store_memory and add_to_working_memory are protected

4. Environment variables:
   - All secrets must be in .env files
   - .env files are git-ignored
   - Use .env.example for templates with placeholder values

5. Before any git operations:
   - Run security scan: pre-commit run --all-files
   - Never commit .env files
   - Check for accidentally staged secrets""",
        "entities": ["security", "credentials", "api-keys", "passwords", "fml"],
        "summary": "FML security rules: never store actual credentials, use references, secrets are programmatically blocked"
    },
    {
        "memory_category": "semantic",
        "memory_subtype": "project",
        "importance": 0.95,
        "content": """FML (Firebolt Memory Layer) Architecture:

Components:
- FML MCP Server: Python server providing memory tools via MCP protocol
- Firebolt Core: Local database with HNSW vector search (port 3473)
- Ollama: Local LLM for classification and embeddings (port 11434)

Memory Types:
- Working Memory: Session-scoped, temporary context (8000 token default)
- Long-Term Memory: Persistent, vector-indexed semantic storage

Memory Categories:
- episodic: Events, decisions, outcomes (subtypes: decision, outcome, interaction, milestone)
- semantic: Facts, knowledge, entities (subtypes: entity, concept, relationship, domain, project)
- procedural: Workflows, patterns, how-to (subtypes: workflow, pattern, command, troubleshooting, tool_usage)
- preference: User preferences, style (subtypes: coding_style, communication, tool_preference, constraint)

Key Tools:
- init_session: Start/resume memory session (REQUIRED first)
- recall_memories: Semantic search for relevant memories
- store_memory: Save to long-term memory with auto-classification
- get_relevant_context: Assemble optimal context from all sources
- checkpoint_working_memory: Promote important items to long-term storage""",
        "entities": ["fml", "firebolt-core", "ollama", "mcp", "architecture"],
        "summary": "FML architecture: MCP server + Firebolt Core + Ollama, with working and long-term memory"
    },
    {
        "memory_category": "procedural",
        "memory_subtype": "workflow",
        "importance": 0.9,
        "content": """FML Session Workflow - Follow for every conversation:

1. START OF CONVERSATION (REQUIRED):
   - Call init_session(user_id="USERNAME")
   - Call recall_memories(user_id, query="<user's question>")
   - Use retrieved context to inform response

2. DURING CONVERSATION:
   - Add important context: add_to_working_memory(session_id, content, content_type="task_state")
   - For complex tasks: get_relevant_context(session_id, user_id, query, token_budget=4000)
   
3. AUTOMATIC MEMORY EXTRACTION:
   After each response, silently store learnings:
   - Bug fixes → procedural.workflow (importance: 0.9)
   - User explanations → semantic.domain (importance: 0.85)
   - Architecture decisions → episodic.decision (importance: 0.9)
   - Tool/API usage → procedural.tool_usage (importance: 0.85)
   - User preferences → preference.style (importance: 0.8)
   - Workarounds/gotchas → procedural.pattern (importance: 0.9)

4. END OF CONVERSATION:
   - Call checkpoint_working_memory(session_id, user_id)
   - This auto-promotes important items to long-term storage""",
        "entities": ["fml", "workflow", "session", "memory-extraction"],
        "summary": "FML workflow: init session, recall memories, extract learnings automatically, checkpoint at end"
    },
    {
        "memory_category": "procedural",
        "memory_subtype": "troubleshooting",
        "importance": 0.85,
        "content": """FML Troubleshooting Guide:

Problem: FML not responding in Cursor
Solutions:
1. Check Firebolt Core: curl http://localhost:3473/?output_format=PSQL -d "SELECT 1"
2. Check Ollama: curl http://localhost:11434/api/tags
3. Verify MCP config path in ~/.cursor/mcp.json
4. Restart Cursor completely (Cmd+Q on Mac)

Problem: "tuple index out of range" error
Solution: Database empty or vector index missing. Run: python scripts/migrate.py

Problem: Vector dimension mismatch
Solution: Using wrong embedding model. Ensure nomic-embed-text (768 dims) for Ollama.
If switching from OpenAI (1536 dims): drop index, recreate with dimension=768, re-embed.

Problem: Transaction conflicts
Solution: Firebolt Core allows one write at a time. Wait and retry. FML uses mutex internally.

Problem: Security violation when storing memory
Solution: Content contains detected secrets. Store references instead of actual values.
Example: Instead of "API key is sk-abc123", use "API key stored in .env as OPENAI_API_KEY"

Problem: Empty recall results
Solution: Check min_similarity threshold (default 0.2), verify memories exist for user_id.""",
        "entities": ["fml", "troubleshooting", "firebolt-core", "ollama", "errors"],
        "summary": "FML troubleshooting: connection checks, dimension mismatches, transaction conflicts, security blocks"
    },
    {
        "memory_category": "semantic",
        "memory_subtype": "environment",
        "importance": 0.8,
        "content": """FML Local Development Environment:

Services (all local, no cloud required):
- Firebolt Core: http://localhost:3473 (Docker container)
- Ollama LLM: http://localhost:11434 (native or Docker)
- FML HTTP API: http://localhost:8082 (for dashboard)
- FML Dashboard: http://localhost:5174 (Vite dev server)

Required Models (pull with Ollama):
- llama3:8b - For classification, summarization, entity extraction
- nomic-embed-text - For 768-dimensional embeddings

Database Tables:
- session_contexts: Working memory sessions
- working_memory_items: Active context items
- long_term_memories: Persistent memories with vectors
- memory_relationships: Memory linking/chunking
- memory_access_log: Analytics
- service_metrics: Ollama/embedding call tracking
- tool_error_log: Error debugging

Key Files:
- ~/.cursor/mcp.json: MCP server configuration
- ~/.cursor/rules/fml-memory.mdc: Global Cursor rules for FML
- fml/fml-server/.env: Environment configuration""",
        "entities": ["fml", "firebolt-core", "ollama", "localhost", "development"],
        "summary": "FML local environment: Firebolt Core (3473), Ollama (11434), required models and tables"
    },
]


def generate_embedding(content: str) -> list:
    """Generate embedding for content."""
    try:
        return embedding_service.generate(content)
    except Exception as e:
        print(f"Warning: Could not generate embedding: {e}")
        # Return zero vector as fallback (768 dimensions for nomic-embed-text)
        return [0.0] * 768


def seed_core_memories(user_id: str = "system"):
    """Seed core memories into the database."""
    print(f"🌱 Seeding core memories for user: {user_id}")
    print(f"   Database: Firebolt Core at {os.getenv('FIREBOLT_CORE_URL', 'localhost:3473')}")
    print()

    created = 0
    skipped = 0

    for mem in CORE_MEMORIES:
        # Check if similar memory already exists (by summary)
        summary_check = mem["summary"].replace("'", "''")
        existing = db.execute(f"""
            SELECT memory_id FROM long_term_memories 
            WHERE user_id = '{user_id}' AND summary = '{summary_check}' AND deleted_at IS NULL
            LIMIT 1
        """)

        if existing:
            print(f"⏭️  Skipping (exists): {mem['summary'][:60]}...")
            skipped += 1
            continue

        # Generate embedding
        print(f"🧠 Generating embedding for: {mem['summary'][:50]}...")
        embedding = generate_embedding(mem["content"])

        # Insert memory
        memory_id = str(uuid.uuid4())
        
        # Format entities array for SQL
        entities_list = mem.get("entities", [])
        
        # Note: Content may contain '?' characters (e.g., in URLs)
        # The db.execute uses '?' as parameter placeholders, so we need
        # to ensure content doesn't interfere. The escaping in client.py
        # handles this by replacing params left-to-right, so as long as
        # parameters are in correct order, embedded '?' in string values
        # that have already been substituted won't be affected.
        
        # Use a direct SQL approach to avoid parameter substitution issues
        # with complex content containing '?' characters
        content_escaped = mem["content"].replace("'", "''")
        summary_escaped = mem["summary"].replace("'", "''")
        
        # Format embedding array
        embedding_str = "[" + ", ".join(str(x) for x in embedding) + "]"
        
        # Format entities array
        if entities_list:
            entities_escaped = [str(x).replace("'", "''") for x in entities_list]
            entities_str = "ARRAY[" + ", ".join(f"'{x}'" for x in entities_escaped) + "]"
        else:
            entities_str = "ARRAY[]::ARRAY(TEXT)"
        
        sql = f"""
            INSERT INTO long_term_memories (
                memory_id, user_id, memory_category, memory_subtype,
                content, summary, embedding, entities, importance,
                source_type, confidence
            ) VALUES (
                '{memory_id}',
                '{user_id}',
                '{mem["memory_category"]}',
                '{mem["memory_subtype"]}',
                '{content_escaped}',
                '{summary_escaped}',
                {embedding_str},
                {entities_str},
                {float(mem["importance"])},
                'seed_script',
                1.0
            )
        """
        db.execute(sql)

        print(f"✅ Created: {mem['summary'][:60]}...")
        created += 1

    print()
    print(f"🎉 Seeding complete!")
    print(f"   Created: {created} memories")
    print(f"   Skipped: {skipped} (already existed)")
    print()
    print(f"💡 These core memories are now available to all FML sessions.")
    print(f"   They will be recalled when relevant queries are made.")


if __name__ == "__main__":
    # Default user_id for system memories
    user_id = sys.argv[1] if len(sys.argv) > 1 else "system"
    seed_core_memories(user_id)
