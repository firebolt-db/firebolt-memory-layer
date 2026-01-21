#!/usr/bin/env python3
"""
Rebuild long_term_memories table with vector index.

In Firebolt Local Core, HNSW indices must be created on an EMPTY table
before any data is inserted. This script:
1. Backs up existing memories to a temp table
2. Drops and recreates long_term_memories
3. Creates the HNSW vector index on the empty table
4. Restores data from backup
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.client import db


def rebuild_with_index():
    """Rebuild the long_term_memories table with proper vector index."""
    
    print("=" * 60)
    print("FML - Rebuild Vector Table")
    print("=" * 60)
    
    # Step 1: Check current state
    print("\n[1/6] Checking current state...")
    try:
        result = db.execute("SELECT COUNT(*) as cnt FROM long_term_memories")
        row_count = result[0]['cnt'] if result else 0
        print(f"       Found {row_count} existing memories")
    except Exception as e:
        print(f"       Table may not exist: {e}")
        row_count = 0
    
    # Step 2: Backup existing data
    if row_count > 0:
        print("\n[2/6] Backing up existing memories...")
        try:
            db.execute("DROP TABLE IF EXISTS long_term_memories_backup")
            db.execute("""
                CREATE TABLE long_term_memories_backup AS
                SELECT * FROM long_term_memories
            """)
            print(f"       ✓ Backed up {row_count} memories")
        except Exception as e:
            print(f"       ✗ Backup failed: {e}")
            return False
    else:
        print("\n[2/6] No data to backup, skipping...")
    
    # Step 3: Drop existing table
    print("\n[3/6] Dropping existing table...")
    try:
        db.execute("DROP TABLE IF EXISTS long_term_memories")
        print("       ✓ Table dropped")
    except Exception as e:
        print(f"       ✗ Drop failed: {e}")
        return False
    
    # Step 4: Create fresh table
    print("\n[4/6] Creating fresh table...")
    # NOTE: related_memories column removed - use memory_relationships table instead
    create_table_sql = """
    CREATE TABLE long_term_memories (
        memory_id       TEXT NOT NULL,
        user_id         TEXT NOT NULL,
        org_id          TEXT,
        memory_category TEXT NOT NULL,
        memory_subtype  TEXT NOT NULL,
        content         TEXT NOT NULL,
        summary         TEXT,
        embedding       ARRAY(REAL NOT NULL) NOT NULL,
        entities        ARRAY(TEXT),
        metadata        TEXT,
        event_time      TIMESTAMPNTZ,
        is_temporal     BOOLEAN DEFAULT FALSE,
        importance      REAL DEFAULT 0.5,
        access_count    INT DEFAULT 0,
        decay_factor    REAL DEFAULT 1.0,
        supersedes      TEXT,
        source_session  TEXT,
        source_type     TEXT,
        confidence      REAL DEFAULT 1.0,
        created_at      TIMESTAMPNTZ DEFAULT CURRENT_TIMESTAMP(),
        last_accessed   TIMESTAMPNTZ DEFAULT CURRENT_TIMESTAMP(),
        updated_at      TIMESTAMPNTZ DEFAULT CURRENT_TIMESTAMP(),
        deleted_at      TIMESTAMPNTZ
    )
    PRIMARY INDEX memory_id
    """
    try:
        db.execute(create_table_sql)
        print("       ✓ Table created")
    except Exception as e:
        print(f"       ✗ Create failed: {e}")
        return False
    
    # Step 5: Create HNSW index on EMPTY table (critical!)
    print("\n[5/6] Creating HNSW vector index on empty table...")
    create_index_sql = """
    CREATE INDEX idx_memories_embedding ON long_term_memories USING HNSW (
        embedding vector_cosine_ops
    ) WITH (
        dimension = 768,
        m = 16,
        ef_construction = 128,
        quantization = 'bf16'
    )
    """
    try:
        db.execute(create_index_sql)
        print("       ✓ HNSW vector index created")
    except Exception as e:
        print(f"       ✗ Index creation failed: {e}")
        return False
    
    # Step 6: Restore data
    if row_count > 0:
        print("\n[6/6] Restoring memories from backup...")
        try:
            db.execute("""
                INSERT INTO long_term_memories 
                SELECT * FROM long_term_memories_backup
            """)
            
            # Verify restoration
            result = db.execute("SELECT COUNT(*) as cnt FROM long_term_memories")
            restored = result[0]['cnt'] if result else 0
            print(f"       ✓ Restored {restored} memories")
            
            # Clean up backup
            db.execute("DROP TABLE IF EXISTS long_term_memories_backup")
            print("       ✓ Cleaned up backup table")
        except Exception as e:
            print(f"       ✗ Restore failed: {e}")
            print("       ⚠ Backup table preserved: long_term_memories_backup")
            return False
    else:
        print("\n[6/6] No data to restore, table ready for use")
    
    print("\n" + "=" * 60)
    print("✓ Vector table rebuilt successfully!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = rebuild_with_index()
    sys.exit(0 if success else 1)
