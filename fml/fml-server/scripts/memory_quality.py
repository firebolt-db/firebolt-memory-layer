#!/usr/bin/env python3
"""
Memory Quality Evaluation for FML.

Helps identify:
1. Potentially contradictory memories on the same topic
2. Stale memories that may need updating
3. Low-value memories (never accessed, low importance)

Run periodically or on-demand to maintain memory quality.
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.client import db
from src.llm.embeddings import embedding_service
from src.llm.ollama import ollama_service


def find_potential_contradictions(user_id: str, similarity_threshold: float = 0.7):
    """
    Find memory pairs that are semantically similar but may contain
    contradictory information (candidates for review).
    
    Strategy: Find memories with high similarity (same topic) but different
    content that might need reconciliation.
    """
    print(f"\n🔍 Finding potential contradictions for user: {user_id}")
    print(f"   Similarity threshold: {similarity_threshold}")
    
    # Get all memories for user
    memories = db.execute("""
        SELECT memory_id, content, memory_category, memory_subtype, 
               importance, created_at, access_count
        FROM long_term_memories
        WHERE user_id = ? AND deleted_at IS NULL
        ORDER BY created_at DESC
    """, (user_id,))
    
    if len(memories) < 2:
        print("   Not enough memories to compare")
        return []
    
    print(f"   Analyzing {len(memories)} memories...")
    
    # Compare each memory against others using embeddings
    contradictions = []
    
    for i, mem1 in enumerate(memories):
        mem1_id, mem1_content, mem1_cat, mem1_sub, mem1_imp, mem1_date, mem1_access = mem1
        
        # Generate embedding for this memory
        emb1 = embedding_service.generate(mem1_content)
        emb_literal = "[" + ", ".join(str(v) for v in emb1) + "]::ARRAY(DOUBLE)"
        
        # Find similar memories (excluding self)
        similar = db.execute(f"""
            SELECT 
                memory_id, content, memory_category, memory_subtype,
                importance, created_at, access_count,
                VECTOR_COSINE_SIMILARITY(embedding, {emb_literal}) as similarity
            FROM long_term_memories
            WHERE user_id = ? 
              AND deleted_at IS NULL
              AND memory_id != ?
              AND memory_category = ?
            ORDER BY similarity DESC
            LIMIT 5
        """, (user_id, mem1_id, mem1_cat))
        
        for mem2 in similar:
            mem2_id, mem2_content, mem2_cat, mem2_sub, mem2_imp, mem2_date, mem2_access, sim = mem2
            
            if sim and sim >= similarity_threshold:
                # High similarity = same topic, check if content differs significantly
                content_overlap = _calculate_content_overlap(mem1_content, mem2_content)
                
                if content_overlap < 0.5:  # Different enough to be potential contradiction
                    contradictions.append({
                        "memory_1": {
                            "id": mem1_id,
                            "content": mem1_content[:200] + "..." if len(mem1_content) > 200 else mem1_content,
                            "created": str(mem1_date),
                            "importance": mem1_imp,
                            "access_count": mem1_access
                        },
                        "memory_2": {
                            "id": mem2_id,
                            "content": mem2_content[:200] + "..." if len(mem2_content) > 200 else mem2_content,
                            "created": str(mem2_date),
                            "importance": mem2_imp,
                            "access_count": mem2_access
                        },
                        "similarity": round(sim, 4),
                        "content_overlap": round(content_overlap, 4),
                        "recommendation": _recommend_action(mem1, mem2, sim, content_overlap)
                    })
        
        # Progress indicator
        if (i + 1) % 10 == 0:
            print(f"   Processed {i + 1}/{len(memories)} memories...")
    
    # Deduplicate (A vs B and B vs A are the same)
    seen = set()
    unique_contradictions = []
    for c in contradictions:
        key = tuple(sorted([c["memory_1"]["id"], c["memory_2"]["id"]]))
        if key not in seen:
            seen.add(key)
            unique_contradictions.append(c)
    
    print(f"   Found {len(unique_contradictions)} potential contradictions")
    return unique_contradictions


def _calculate_content_overlap(content1: str, content2: str) -> float:
    """Calculate word overlap between two content strings."""
    words1 = set(content1.lower().split())
    words2 = set(content2.lower().split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = words1 & words2
    union = words1 | words2
    
    return len(intersection) / len(union)  # Jaccard similarity


def _recommend_action(mem1, mem2, similarity: float, overlap: float) -> str:
    """Recommend action based on memory comparison."""
    mem1_date = mem1[5]
    mem2_date = mem2[5]
    mem1_access = mem1[6]
    mem2_access = mem2[6]
    mem1_imp = mem1[4]
    mem2_imp = mem2[4]
    
    # Newer memory generally preferred
    newer_id = mem1[0] if mem1_date > mem2_date else mem2[0]
    older_id = mem2[0] if mem1_date > mem2_date else mem1[0]
    
    # More accessed memory has proven value
    more_accessed = mem1[0] if mem1_access > mem2_access else mem2[0]
    
    if similarity > 0.9:
        return f"MERGE: Very similar - consider merging into one comprehensive memory"
    elif mem1_access == 0 and mem2_access > 2:
        return f"SUPERSEDE: Keep {more_accessed} (more useful), mark {mem1[0]} as superseded"
    elif mem2_access == 0 and mem1_access > 2:
        return f"SUPERSEDE: Keep {more_accessed} (more useful), mark {mem2[0]} as superseded"
    elif mem1_date > mem2_date:
        return f"REVIEW: {newer_id} is newer - verify if it supersedes {older_id}"
    else:
        return f"REVIEW: Manual review needed - both memories may be valid"


def find_stale_memories(user_id: str, days_threshold: int = 30):
    """
    Find memories that haven't been accessed in a while
    and may need review or archival.
    """
    print(f"\n🕐 Finding stale memories (not accessed in {days_threshold} days)")
    
    cutoff_date = datetime.now() - timedelta(days=days_threshold)
    
    stale = db.execute("""
        SELECT memory_id, content, memory_category, importance, 
               access_count, created_at, last_accessed
        FROM long_term_memories
        WHERE user_id = ? 
          AND deleted_at IS NULL
          AND (last_accessed < ? OR last_accessed IS NULL)
          AND access_count < 2
        ORDER BY importance ASC, access_count ASC
        LIMIT 20
    """, (user_id, cutoff_date.isoformat()))
    
    print(f"   Found {len(stale)} stale memories")
    
    return [{
        "memory_id": row[0],
        "content": row[1][:150] + "..." if len(row[1]) > 150 else row[1],
        "category": row[2],
        "importance": row[3],
        "access_count": row[4],
        "created_at": str(row[5]),
        "last_accessed": str(row[6]) if row[6] else "Never",
        "recommendation": "REVIEW: Low access count and old - verify still relevant"
    } for row in stale]


def supersede_memory(old_memory_id: str, new_memory_id: str, user_id: str):
    """
    Mark an old memory as superseded by a newer one.
    The old memory is soft-deleted but the relationship is tracked.
    """
    print(f"\n🔄 Superseding memory {old_memory_id} with {new_memory_id}")
    
    # Verify both memories exist and belong to user
    old = db.execute(
        "SELECT memory_id FROM long_term_memories WHERE memory_id = ? AND user_id = ? AND deleted_at IS NULL",
        (old_memory_id, user_id)
    )
    new = db.execute(
        "SELECT memory_id FROM long_term_memories WHERE memory_id = ? AND user_id = ? AND deleted_at IS NULL",
        (new_memory_id, user_id)
    )
    
    if not old:
        print(f"   ❌ Old memory {old_memory_id} not found")
        return False
    if not new:
        print(f"   ❌ New memory {new_memory_id} not found")
        return False
    
    # Update the new memory to reference what it supersedes
    db.execute("""
        UPDATE long_term_memories
        SET supersedes = ?
        WHERE memory_id = ?
    """, (old_memory_id, new_memory_id))
    
    # Soft-delete the old memory
    db.execute("""
        UPDATE long_term_memories
        SET deleted_at = CURRENT_TIMESTAMP()
        WHERE memory_id = ?
    """, (old_memory_id,))
    
    print(f"   ✅ Memory {old_memory_id} superseded by {new_memory_id}")
    return True


def apply_decay(user_id: str, decay_rate: float = 0.95):
    """
    Apply importance decay to memories that haven't been accessed recently.
    Memories that are accessed frequently maintain their importance.
    """
    print(f"\n📉 Applying decay (rate: {decay_rate}) to unused memories")
    
    # Decay memories not accessed in last 7 days
    cutoff = datetime.now() - timedelta(days=7)
    
    result = db.execute("""
        UPDATE long_term_memories
        SET importance = importance * ?,
            decay_factor = decay_factor * ?
        WHERE user_id = ?
          AND deleted_at IS NULL
          AND last_accessed < ?
          AND importance > 0.1
        RETURNING memory_id
    """, (decay_rate, decay_rate, user_id, cutoff.isoformat()))
    
    decayed_count = len(result) if result else 0
    print(f"   Applied decay to {decayed_count} memories")
    
    return decayed_count


def generate_quality_report(user_id: str):
    """Generate a comprehensive memory quality report."""
    
    print("\n" + "=" * 60)
    print(f"📊 Memory Quality Report for: {user_id}")
    print(f"   Generated: {datetime.now().isoformat()}")
    print("=" * 60)
    
    # Overall stats
    stats = db.execute("""
        SELECT 
            COUNT(*) as total,
            AVG(importance) as avg_importance,
            AVG(access_count) as avg_access,
            SUM(CASE WHEN access_count = 0 THEN 1 ELSE 0 END) as never_accessed,
            SUM(CASE WHEN importance < 0.3 THEN 1 ELSE 0 END) as low_importance
        FROM long_term_memories
        WHERE user_id = ? AND deleted_at IS NULL
    """, (user_id,))
    
    if stats:
        row = stats[0]
        print(f"\n📈 Overall Statistics:")
        print(f"   Total memories: {row[0]}")
        print(f"   Avg importance: {row[1]:.2f}" if row[1] else "   Avg importance: N/A")
        print(f"   Avg access count: {row[2]:.1f}" if row[2] else "   Avg access count: N/A")
        print(f"   Never accessed: {row[3]}")
        print(f"   Low importance (<0.3): {row[4]}")
    
    # Category distribution
    categories = db.execute("""
        SELECT memory_category, COUNT(*), AVG(importance), AVG(access_count)
        FROM long_term_memories
        WHERE user_id = ? AND deleted_at IS NULL
        GROUP BY memory_category
    """, (user_id,))
    
    print(f"\n📁 By Category:")
    for cat in categories:
        print(f"   {cat[0]}: {cat[1]} memories (avg imp: {cat[2]:.2f}, avg access: {cat[3]:.1f})")
    
    # Find issues
    contradictions = find_potential_contradictions(user_id)
    stale = find_stale_memories(user_id)
    
    print(f"\n⚠️  Issues Found:")
    print(f"   Potential contradictions: {len(contradictions)}")
    print(f"   Stale memories: {len(stale)}")
    
    return {
        "user_id": user_id,
        "generated_at": datetime.now().isoformat(),
        "total_memories": stats[0][0] if stats else 0,
        "contradictions": contradictions[:5],  # Top 5
        "stale_memories": stale[:5],  # Top 5
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python memory_quality.py <user_id> [command]")
        print("\nCommands:")
        print("  report              - Generate quality report (default)")
        print("  contradictions      - Find potential contradictions")
        print("  stale               - Find stale memories")
        print("  decay               - Apply importance decay")
        print("  supersede OLD NEW   - Mark OLD as superseded by NEW")
        sys.exit(1)
    
    user_id = sys.argv[1]
    command = sys.argv[2] if len(sys.argv) > 2 else "report"
    
    if command == "report":
        report = generate_quality_report(user_id)
        print("\n" + json.dumps(report, indent=2, default=str))
    elif command == "contradictions":
        results = find_potential_contradictions(user_id)
        print("\n" + json.dumps(results, indent=2, default=str))
    elif command == "stale":
        results = find_stale_memories(user_id)
        print("\n" + json.dumps(results, indent=2, default=str))
    elif command == "decay":
        apply_decay(user_id)
    elif command == "supersede":
        if len(sys.argv) < 5:
            print("Usage: python memory_quality.py <user_id> supersede <old_id> <new_id>")
            sys.exit(1)
        supersede_memory(sys.argv[3], sys.argv[4], user_id)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
