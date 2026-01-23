-- ============================================================
-- FML Server Database Schema for Firebolt
-- Uses Firebolt-specific syntax (PRIMARY INDEX, no PRIMARY KEY)
-- ============================================================

-- ============================================================
-- WORKING MEMORY TABLES
-- ============================================================

-- Session management
CREATE TABLE IF NOT EXISTS session_contexts (
    session_id      TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    org_id          TEXT,

    total_tokens    INT DEFAULT 0,
    max_tokens      INT DEFAULT 8000,

    created_at      TIMESTAMPNTZ DEFAULT CURRENT_TIMESTAMP(),
    last_activity   TIMESTAMPNTZ DEFAULT CURRENT_TIMESTAMP(),
    expires_at      TIMESTAMPNTZ,

    config          TEXT
)
PRIMARY INDEX session_id;

-- Working memory items
CREATE TABLE IF NOT EXISTS working_memory_items (
    item_id         TEXT NOT NULL,
    session_id      TEXT NOT NULL,
    user_id         TEXT NOT NULL,

    content_type    TEXT NOT NULL,
    content         TEXT NOT NULL,
    token_count     INT NOT NULL,

    relevance_score REAL DEFAULT 1.0,
    pinned          BOOLEAN DEFAULT FALSE,

    sequence_num    INT NOT NULL,
    created_at      TIMESTAMPNTZ DEFAULT CURRENT_TIMESTAMP(),
    last_accessed   TIMESTAMPNTZ DEFAULT CURRENT_TIMESTAMP()
)
PRIMARY INDEX item_id;


-- ============================================================
-- LONG-TERM MEMORY TABLES
-- ============================================================

-- Main memory table with vector embeddings
-- NOTE: embedding column is NOT NULL to support HNSW vector search index
CREATE TABLE IF NOT EXISTS long_term_memories (
    memory_id       TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    org_id          TEXT,

    -- Memory classification (human-aligned taxonomy)
    memory_category TEXT NOT NULL,
    memory_subtype  TEXT NOT NULL,

    -- Content
    content         TEXT NOT NULL,
    summary         TEXT,

    -- Vector embedding: ARRAY(REAL NOT NULL) NOT NULL for 1536-dim OpenAI embeddings
    -- Must be NOT NULL (inner and outer) to support vector search index
    embedding       ARRAY(REAL NOT NULL) NOT NULL,

    -- Named entities for precise retrieval
    entities        ARRAY(TEXT),

    -- Metadata as JSON string
    metadata        TEXT,

    -- Temporal context
    event_time      TIMESTAMPNTZ,
    is_temporal     BOOLEAN DEFAULT FALSE,

    -- Importance & access patterns
    importance      REAL DEFAULT 0.5,
    access_count    INT DEFAULT 0,
    decay_factor    REAL DEFAULT 1.0,

    -- Relationships
    -- NOTE: related_memories column removed due to Firebolt Core bug with NULL arrays
    -- causing "Secondary file s3://...related_memories.null1.bin does not exist" errors
    supersedes      TEXT,

    -- Source tracking
    source_session  TEXT,
    source_type     TEXT,
    confidence      REAL DEFAULT 1.0,

    -- Timestamps
    created_at      TIMESTAMPNTZ DEFAULT CURRENT_TIMESTAMP(),
    last_accessed   TIMESTAMPNTZ DEFAULT CURRENT_TIMESTAMP(),
    updated_at      TIMESTAMPNTZ DEFAULT CURRENT_TIMESTAMP(),

    -- Soft delete
    deleted_at      TIMESTAMPNTZ
)
PRIMARY INDEX memory_id;

-- HNSW Vector Search Index for fast semantic similarity search
-- Must be created on empty table before inserting data (Firebolt 4.28)
-- Uses cosine distance for Ollama nomic-embed-text embeddings (768 dimensions)
-- Note: OpenAI embeddings are 1536 dimensions if using that instead
CREATE INDEX idx_memories_embedding ON long_term_memories USING HNSW (
    embedding vector_cosine_ops
) WITH (
    dimension = 768,
    m = 16,
    ef_construction = 128,
    quantization = 'bf16'
);


-- Memory relationships (join table for memory linking/chunking)
-- Supports the cognitive "Chunking" principle: related items grouped together
-- Uses join table instead of array column to avoid Firebolt Core NULL array bugs
CREATE TABLE IF NOT EXISTS memory_relationships (
    relationship_id TEXT NOT NULL,
    source_id       TEXT NOT NULL,      -- The memory creating the relationship
    target_id       TEXT NOT NULL,      -- The memory being linked to
    user_id         TEXT NOT NULL,      -- Owner (for authorization)
    
    -- Relationship type for flexible linking
    relationship    TEXT NOT NULL,      -- 'related_to', 'part_of', 'depends_on', 'contradicts', 'updates'
    
    -- Optional context
    strength        REAL DEFAULT 1.0,   -- Relationship strength (0.0-1.0)
    context         TEXT,               -- Why these are related
    
    created_at      TIMESTAMPNTZ DEFAULT CURRENT_TIMESTAMP(),
    created_by      TEXT                -- Session or process that created this
)
PRIMARY INDEX relationship_id;


-- Memory access log for analytics
CREATE TABLE IF NOT EXISTS memory_access_log (
    access_id       TEXT NOT NULL,
    memory_id       TEXT NOT NULL,
    session_id      TEXT NOT NULL,
    user_id         TEXT NOT NULL,

    query_text      TEXT,
    similarity_score REAL,

    was_useful      BOOLEAN,
    was_used        BOOLEAN,

    accessed_at     TIMESTAMPNTZ DEFAULT CURRENT_TIMESTAMP()
)
PRIMARY INDEX access_id;


-- Tool error log for debugging and review
CREATE TABLE IF NOT EXISTS tool_error_log (
    error_id        TEXT NOT NULL,
    tool_name       TEXT NOT NULL,
    user_id         TEXT,
    error_type      TEXT,
    error_message   TEXT NOT NULL,
    input_preview   TEXT,
    stack_trace     TEXT,
    created_at      TIMESTAMPNTZ DEFAULT CURRENT_TIMESTAMP()
)
PRIMARY INDEX error_id;


-- Service metrics for Ollama/embedding call tracking (cross-process visibility)
CREATE TABLE IF NOT EXISTS service_metrics (
    metric_id       TEXT NOT NULL,
    service         TEXT NOT NULL,       -- 'ollama', 'embedding'
    operation       TEXT NOT NULL,       -- 'classify', 'summarize', 'embed', etc.
    latency_ms      REAL NOT NULL,
    success         BOOLEAN DEFAULT TRUE,
    error_msg       TEXT,
    tokens_in       INT,
    tokens_out      INT,
    recorded_at     TIMESTAMPNTZ DEFAULT CURRENT_TIMESTAMP()
)
PRIMARY INDEX metric_id;
