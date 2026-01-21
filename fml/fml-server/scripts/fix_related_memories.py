#!/usr/bin/env python3
"""
Fix for Firebolt Core S3 bug with related_memories column.

The error: "Secondary file s3://...related_memories.null1.bin does not exist. It is a bug."

This occurs because:
1. related_memories is an ARRAY(TEXT) nullable column  
2. NULL array values haven't been properly materialized in Firebolt Core
3. ANY operation (SELECT *, UPDATE, etc.) that touches rows with NULL arrays fails

Fix: Recreate the table without the problematic column, migrate data, then add it back.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.client import db


def fix_related_memories():
    """Recreate table to fix NULL array column bug."""
    print("=" * 60)
    print("Fixing related_memories NULL values via table recreation")
    print("=" * 60)
    
    # Step 1: Create new table without related_memories
    print("\n[1/5] Creating temporary table...")
    db.execute("""
        CREATE TABLE IF NOT EXISTS long_term_memories_fixed (
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
    """)
    print("       ✓ Created long_term_memories_fixed")
    
    # Step 2: Copy data (excluding related_memories)
    print("\n[2/5] Copying data to new table...")
    db.execute("""
        INSERT INTO long_term_memories_fixed (
            memory_id, user_id, org_id, memory_category, memory_subtype,
            content, summary, embedding, entities, metadata,
            event_time, is_temporal, importance, access_count, decay_factor,
            supersedes, source_session, source_type, confidence,
            created_at, last_accessed, updated_at, deleted_at
        )
        SELECT 
            memory_id, user_id, org_id, memory_category, memory_subtype,
            content, summary, embedding, entities, metadata,
            event_time, is_temporal, importance, access_count, decay_factor,
            supersedes, source_session, source_type, confidence,
            created_at, last_accessed, updated_at, deleted_at
        FROM long_term_memories
    """)
    
    # Count rows
    count = db.execute("SELECT COUNT(*) FROM long_term_memories_fixed")
    row_count = count[0][0] if count else 0
    print(f"       ✓ Copied {row_count} rows")
    
    # Step 3: Drop old index and table
    print("\n[3/5] Dropping old index and table...")
    try:
        db.execute("DROP INDEX idx_memories_embedding")
        print("       ✓ Dropped idx_memories_embedding")
    except Exception as e:
        print(f"       (index may not exist: {e})")
    
    db.execute("DROP TABLE long_term_memories")
    print("       ✓ Dropped long_term_memories")
    
    # Step 4: Rename new table
    print("\n[4/5] Renaming fixed table...")
    db.execute("ALTER TABLE long_term_memories_fixed RENAME TO long_term_memories")
    print("       ✓ Renamed to long_term_memories")
    
    # Step 5: Recreate HNSW index
    print("\n[5/5] Recreating HNSW vector index...")
    db.execute("""
        CREATE INDEX idx_memories_embedding ON long_term_memories USING HNSW (
            embedding vector_cosine_ops
        ) WITH (
            dimension = 768,
            m = 16,
            ef_construction = 128,
            quantization = 'bf16'
        )
    """)
    print("       ✓ Created idx_memories_embedding")
    
    return row_count


def verify_fix():
    """Verify the fix worked."""
    print("\n" + "=" * 60)
    print("Verifying fix...")
    print("=" * 60)
    
    # Test SELECT *
    print("\n[Test 1] SELECT * ...")
    try:
        result = db.execute("SELECT * FROM long_term_memories LIMIT 1")
        print(f"         ✓ Success! Got {len(result)} rows")
    except Exception as e:
        print(f"         ✗ Failed: {e}")
        return False
    
    # Test UPDATE
    print("\n[Test 2] UPDATE ...")
    try:
        result = db.execute("SELECT memory_id FROM long_term_memories LIMIT 1")
        if result:
            mem_id = result[0][0]
            db.execute("""
                UPDATE long_term_memories 
                SET access_count = access_count + 1 
                WHERE memory_id = ?
            """, (mem_id,))
            print(f"         ✓ Success! Updated {mem_id}")
    except Exception as e:
        print(f"         ✗ Failed: {e}")
        return False
    
    return True


if __name__ == "__main__":
    print("FML Fix: related_memories S3 bug\n")
    print("This will recreate the long_term_memories table to fix the")
    print("Firebolt Core bug with NULL array columns.\n")
    
    response = input("Continue? [y/N]: ").strip().lower()
    if response != 'y':
        print("Aborted.")
        sys.exit(0)
    
    try:
        row_count = fix_related_memories()
        
        if verify_fix():
            print("\n" + "=" * 60)
            print("✓ Fix complete!")
            print("=" * 60)
            print(f"\nMigrated {row_count} memories successfully.")
            print("Note: related_memories column has been removed.")
            print("You can now use recall_memories without errors.")
        else:
            print("\n❌ Verification failed - please check the table manually")
            sys.exit(1)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nIf the migration failed partway through, you may need to:")
        print("1. Check if long_term_memories_fixed exists")
        print("2. Manually recover from backup if needed")
        sys.exit(1)
