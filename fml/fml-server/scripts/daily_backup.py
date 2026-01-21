#!/usr/bin/env python3
"""
Daily backup script for FML long-term memories.

Incrementally backs up new memories to long_term_memories_backup table.
Run daily via cron or manually.
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.client import db


def daily_backup():
    """Backup new memories since last backup."""
    
    print("=" * 60)
    print(f"FML Daily Backup - {datetime.now().isoformat()}")
    print("=" * 60)
    
    # Step 1: Ensure backup table exists
    print("\n[1/4] Checking backup table...")
    try:
        result = db.execute("SELECT COUNT(*) FROM long_term_memories_backup")
        backup_count = result[0][0] if result else 0
        print(f"       Backup table has {backup_count} memories")
    except Exception as e:
        print(f"       Creating backup table...")
        db.execute("""
            CREATE TABLE IF NOT EXISTS long_term_memories_backup AS
            SELECT * FROM long_term_memories WHERE 1=0
        """)
        backup_count = 0
        print("       ✓ Backup table created")
    
    # Step 2: Count current memories
    print("\n[2/4] Checking current memories...")
    result = db.execute("SELECT COUNT(*) FROM long_term_memories")
    current_count = result[0][0] if result else 0
    print(f"       Current table has {current_count} memories")
    
    # Step 3: Find new memories not in backup
    print("\n[3/4] Finding new memories to backup...")
    result = db.execute("""
        SELECT COUNT(*) FROM long_term_memories m
        WHERE NOT EXISTS (
            SELECT 1 FROM long_term_memories_backup b 
            WHERE b.memory_id = m.memory_id
        )
    """)
    new_count = result[0][0] if result else 0
    print(f"       Found {new_count} new memories to backup")
    
    # Step 4: Backup new memories
    if new_count > 0:
        print("\n[4/4] Backing up new memories...")
        db.execute("""
            INSERT INTO long_term_memories_backup
            SELECT * FROM long_term_memories m
            WHERE NOT EXISTS (
                SELECT 1 FROM long_term_memories_backup b 
                WHERE b.memory_id = m.memory_id
            )
        """)
        
        # Also update any modified memories
        # (memories that exist in both but have been updated)
        db.execute("""
            DELETE FROM long_term_memories_backup
            WHERE memory_id IN (
                SELECT m.memory_id FROM long_term_memories m
                JOIN long_term_memories_backup b ON m.memory_id = b.memory_id
                WHERE m.updated_at > b.updated_at
            )
        """)
        db.execute("""
            INSERT INTO long_term_memories_backup
            SELECT * FROM long_term_memories m
            WHERE NOT EXISTS (
                SELECT 1 FROM long_term_memories_backup b 
                WHERE b.memory_id = m.memory_id
            )
        """)
        
        print(f"       ✓ Backed up {new_count} memories")
    else:
        print("\n[4/4] No new memories to backup")
    
    # Final count
    result = db.execute("SELECT COUNT(*) FROM long_term_memories_backup")
    final_backup_count = result[0][0] if result else 0
    
    print("\n" + "=" * 60)
    print(f"✓ Backup complete!")
    print(f"  - Main table: {current_count} memories")
    print(f"  - Backup table: {final_backup_count} memories")
    print(f"  - New this run: {new_count}")
    print("=" * 60)
    
    return new_count


if __name__ == "__main__":
    backed_up = daily_backup()
    sys.exit(0)
