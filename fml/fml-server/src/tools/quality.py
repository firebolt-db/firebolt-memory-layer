"""Memory quality evaluation MCP tools."""

import json
from datetime import datetime, timedelta
from typing import Optional
from mcp.server.fastmcp import FastMCP

from src.db.client import db
from src.llm.embeddings import embedding_service


def register_quality_tools(mcp: FastMCP):
    """Register memory quality tools with the MCP server."""

    @mcp.tool()
    async def memory_quality_report(
        user_id: str,
        include_contradictions: bool = True,
        include_stale: bool = True
    ) -> str:
        """
        Generate a memory quality report for a user.
        
        Analyzes memory health including:
        - Overall statistics (count, importance, access patterns)
        - Category distribution
        - Potential contradictions (similar but different content)
        - Stale memories (not accessed recently)
        
        Args:
            user_id: User whose memories to analyze
            include_contradictions: Whether to scan for contradictions (slower)
            include_stale: Whether to find stale memories
            
        Returns:
            JSON with quality report and recommendations
        """
        report = {
            "user_id": user_id,
            "generated_at": datetime.now().isoformat(),
        }
        
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
        
        if stats and stats[0]:
            row = stats[0]
            report["statistics"] = {
                "total_memories": row[0],
                "avg_importance": round(float(row[1]), 2) if row[1] else 0,
                "avg_access_count": round(float(row[2]), 1) if row[2] else 0,
                "never_accessed": row[3] or 0,
                "low_importance": row[4] or 0
            }
        
        # Category distribution
        categories = db.execute("""
            SELECT memory_category, COUNT(*), AVG(importance), AVG(access_count)
            FROM long_term_memories
            WHERE user_id = ? AND deleted_at IS NULL
            GROUP BY memory_category
        """, (user_id,))
        
        report["by_category"] = {
            row[0]: {
                "count": row[1],
                "avg_importance": round(float(row[2]), 2) if row[2] else 0,
                "avg_access": round(float(row[3]), 1) if row[3] else 0
            }
            for row in categories
        }
        
        # Find stale memories
        if include_stale:
            cutoff = datetime.now() - timedelta(days=30)
            stale = db.execute("""
                SELECT memory_id, content, memory_category, importance, access_count
                FROM long_term_memories
                WHERE user_id = ? 
                  AND deleted_at IS NULL
                  AND (last_accessed < ? OR last_accessed IS NULL)
                  AND access_count < 2
                ORDER BY importance ASC
                LIMIT 5
            """, (user_id, cutoff.isoformat()))
            
            report["stale_memories"] = [{
                "memory_id": row[0],
                "content_preview": row[1][:100] + "..." if len(row[1]) > 100 else row[1],
                "category": row[2],
                "importance": row[3],
                "access_count": row[4]
            } for row in stale]
        
        # Find potential contradictions (simplified - top 5 similar pairs)
        if include_contradictions:
            report["potential_contradictions"] = await _find_top_contradictions(user_id, limit=5)
        
        # Health score (0-100)
        health_score = _calculate_health_score(report)
        report["health_score"] = health_score
        report["health_status"] = (
            "Excellent" if health_score >= 90 else
            "Good" if health_score >= 70 else
            "Fair" if health_score >= 50 else
            "Needs Attention"
        )
        
        return json.dumps(report, indent=2)

    @mcp.tool()
    async def find_memory_contradictions(
        user_id: str,
        similarity_threshold: float = 0.75,
        limit: int = 10
    ) -> str:
        """
        Find memories that may contain contradictory or outdated information.
        
        Identifies memory pairs that are semantically similar (same topic)
        but have different content, suggesting one may supersede the other.
        
        Args:
            user_id: User whose memories to analyze
            similarity_threshold: Min similarity to consider (0.0-1.0, default 0.75)
            limit: Max contradictions to return
            
        Returns:
            JSON with potential contradictions and recommendations
        """
        contradictions = await _find_top_contradictions(
            user_id, 
            threshold=similarity_threshold, 
            limit=limit
        )
        
        return json.dumps({
            "user_id": user_id,
            "threshold": similarity_threshold,
            "found": len(contradictions),
            "contradictions": contradictions
        }, indent=2)

    @mcp.tool()
    async def supersede_memory(
        old_memory_id: str,
        new_memory_id: str,
        user_id: str
    ) -> str:
        """
        Mark an old memory as superseded by a newer, more accurate one.
        
        The old memory is soft-deleted and the relationship is tracked.
        Use this when you've learned new information that invalidates old knowledge.
        
        Args:
            old_memory_id: ID of the outdated memory to supersede
            new_memory_id: ID of the newer, more accurate memory
            user_id: User who owns both memories (for authorization)
            
        Returns:
            JSON with success status
        """
        # Verify both memories exist and belong to user
        old = db.execute(
            "SELECT memory_id, content FROM long_term_memories WHERE memory_id = ? AND user_id = ? AND deleted_at IS NULL",
            (old_memory_id, user_id)
        )
        new = db.execute(
            "SELECT memory_id, content FROM long_term_memories WHERE memory_id = ? AND user_id = ? AND deleted_at IS NULL",
            (new_memory_id, user_id)
        )
        
        if not old:
            return json.dumps({"error": f"Old memory {old_memory_id} not found or already deleted"})
        if not new:
            return json.dumps({"error": f"New memory {new_memory_id} not found"})
        
        # Update the new memory to track what it supersedes
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
        
        return json.dumps({
            "success": True,
            "superseded": {
                "memory_id": old_memory_id,
                "content_preview": old[0][1][:100] + "..." if len(old[0][1]) > 100 else old[0][1]
            },
            "kept": {
                "memory_id": new_memory_id,
                "content_preview": new[0][1][:100] + "..." if len(new[0][1]) > 100 else new[0][1]
            }
        }, indent=2)

    @mcp.tool()
    async def apply_memory_decay(
        user_id: str,
        decay_rate: float = 0.95,
        days_inactive: int = 7
    ) -> str:
        """
        Apply importance decay to memories not accessed recently.
        
        Memories that aren't being used gradually decrease in importance,
        making room for more relevant knowledge. Frequently accessed 
        memories maintain their importance.
        
        Args:
            user_id: User whose memories to decay
            decay_rate: Multiplier for importance (0.0-1.0, default 0.95)
            days_inactive: Days without access before decay applies (default 7)
            
        Returns:
            JSON with number of memories affected
        """
        cutoff = datetime.now() - timedelta(days=days_inactive)
        
        # Get count before
        before = db.execute("""
            SELECT COUNT(*) FROM long_term_memories
            WHERE user_id = ? 
              AND deleted_at IS NULL
              AND (last_accessed < ? OR last_accessed IS NULL)
              AND importance > 0.1
        """, (user_id, cutoff.isoformat()))
        
        affected_count = before[0][0] if before else 0
        
        if affected_count > 0:
            db.execute("""
                UPDATE long_term_memories
                SET importance = importance * ?,
                    decay_factor = decay_factor * ?
                WHERE user_id = ?
                  AND deleted_at IS NULL
                  AND (last_accessed < ? OR last_accessed IS NULL)
                  AND importance > 0.1
            """, (decay_rate, decay_rate, user_id, cutoff.isoformat()))
        
        return json.dumps({
            "success": True,
            "memories_decayed": affected_count,
            "decay_rate": decay_rate,
            "days_inactive_threshold": days_inactive
        })

    @mcp.tool()
    async def run_daily_maintenance(
        user_id: str
    ) -> str:
        """
        Run daily memory maintenance tasks.
        
        Performs:
        1. Backup new memories to backup table
        2. Apply decay to unused memories
        3. Generate quality report
        
        Designed to be called by scheduled jobs (cron).
        
        Args:
            user_id: User whose memories to maintain
            
        Returns:
            JSON with maintenance report
        """
        results = {
            "user_id": user_id,
            "run_at": datetime.now().isoformat(),
            "tasks": {}
        }
        
        # Task 1: Backup new memories
        try:
            # Check backup table exists
            try:
                db.execute("SELECT 1 FROM long_term_memories_backup LIMIT 1")
            except:
                db.execute("""
                    CREATE TABLE IF NOT EXISTS long_term_memories_backup AS
                    SELECT * FROM long_term_memories WHERE 1=0
                """)
            
            # Count new memories to backup
            new_count = db.execute("""
                SELECT COUNT(*) FROM long_term_memories m
                WHERE NOT EXISTS (
                    SELECT 1 FROM long_term_memories_backup b 
                    WHERE b.memory_id = m.memory_id
                )
            """)
            new_memories = int(new_count[0][0]) if new_count else 0
            
            if new_memories > 0:
                db.execute("""
                    INSERT INTO long_term_memories_backup
                    SELECT * FROM long_term_memories m
                    WHERE NOT EXISTS (
                        SELECT 1 FROM long_term_memories_backup b 
                        WHERE b.memory_id = m.memory_id
                    )
                """)
            
            results["tasks"]["backup"] = {
                "success": True,
                "new_memories_backed_up": new_memories
            }
        except Exception as e:
            results["tasks"]["backup"] = {
                "success": False,
                "error": str(e)
            }
        
        # Task 2: Apply decay
        try:
            cutoff = datetime.now() - timedelta(days=7)
            decay_result = db.execute("""
                SELECT COUNT(*) FROM long_term_memories
                WHERE user_id = ? 
                  AND deleted_at IS NULL
                  AND (last_accessed < ? OR last_accessed IS NULL)
                  AND importance > 0.1
            """, (user_id, cutoff.isoformat()))
            
            decayed = int(decay_result[0][0]) if decay_result else 0
            
            if decayed > 0:
                db.execute("""
                    UPDATE long_term_memories
                    SET importance = importance * 0.98,
                        decay_factor = decay_factor * 0.98
                    WHERE user_id = ?
                      AND deleted_at IS NULL
                      AND (last_accessed < ? OR last_accessed IS NULL)
                      AND importance > 0.1
                """, (user_id, cutoff.isoformat()))
            
            results["tasks"]["decay"] = {
                "success": True,
                "memories_decayed": decayed,
                "decay_rate": 0.98
            }
        except Exception as e:
            results["tasks"]["decay"] = {
                "success": False,
                "error": str(e)
            }
        
        # Task 3: Quality stats
        try:
            stats = db.execute("""
                SELECT 
                    COUNT(*),
                    AVG(importance),
                    SUM(CASE WHEN access_count = 0 THEN 1 ELSE 0 END)
                FROM long_term_memories
                WHERE user_id = ? AND deleted_at IS NULL
            """, (user_id,))
            
            if stats and stats[0]:
                results["tasks"]["quality_check"] = {
                    "success": True,
                    "total_memories": stats[0][0],
                    "avg_importance": round(float(stats[0][1]), 2) if stats[0][1] else 0,
                    "never_accessed": stats[0][2] or 0
                }
        except Exception as e:
            results["tasks"]["quality_check"] = {
                "success": False,
                "error": str(e)
            }
        
        results["overall_success"] = all(
            t.get("success", False) for t in results["tasks"].values()
        )
        
        return json.dumps(results, indent=2)


async def _find_top_contradictions(
    user_id: str, 
    threshold: float = 0.75, 
    limit: int = 5
) -> list:
    """Find top potential contradictions for a user."""
    
    # Get recent memories to check
    memories = db.execute("""
        SELECT memory_id, content, memory_category, importance, created_at
        FROM long_term_memories
        WHERE user_id = ? AND deleted_at IS NULL
        ORDER BY created_at DESC
        LIMIT 20
    """, (user_id,))
    
    if len(memories) < 2:
        return []
    
    contradictions = []
    seen_pairs = set()
    
    for mem in memories[:10]:  # Check 10 most recent
        mem_id, content, category, importance, created = mem
        
        # Generate embedding
        embedding = embedding_service.generate(content)
        emb_literal = "[" + ", ".join(str(v) for v in embedding) + "]::ARRAY(DOUBLE)"
        
        # Find similar in same category
        # Note: Explicitly select only needed columns to avoid Firebolt Core bug
        # with NULL array columns (related_memories) that causes S3 file errors
        similar = db.execute(f"""
            SELECT 
                memory_id, content, importance, created_at,
                VECTOR_COSINE_SIMILARITY(embedding, {emb_literal}) as similarity
            FROM long_term_memories
            WHERE user_id = ? 
              AND deleted_at IS NULL
              AND memory_id != ?
              AND memory_category = ?
            ORDER BY similarity DESC
            LIMIT 3
        """, (user_id, mem_id, category))
        
        for sim_mem in similar:
            sim_id, sim_content, sim_imp, sim_created, similarity = sim_mem
            
            if similarity and similarity >= threshold:
                pair_key = tuple(sorted([mem_id, sim_id]))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                
                # Calculate content overlap
                words1 = set(content.lower().split())
                words2 = set(sim_content.lower().split())
                overlap = len(words1 & words2) / len(words1 | words2) if words1 | words2 else 0
                
                if overlap < 0.5:  # Different enough content
                    newer_id = mem_id if created > sim_created else sim_id
                    older_id = sim_id if created > sim_created else mem_id
                    
                    contradictions.append({
                        "newer_memory": {
                            "id": newer_id,
                            "content": (content if newer_id == mem_id else sim_content)[:150] + "..."
                        },
                        "older_memory": {
                            "id": older_id,
                            "content": (sim_content if older_id == sim_id else content)[:150] + "..."
                        },
                        "similarity": round(similarity, 4),
                        "recommendation": f"Review if {newer_id} supersedes {older_id}"
                    })
                    
                    if len(contradictions) >= limit:
                        return contradictions
    
    return contradictions


def _calculate_health_score(report: dict) -> int:
    """Calculate overall memory health score (0-100)."""
    score = 100
    
    stats = report.get("statistics", {})
    
    # Penalize low importance average
    avg_imp = float(stats.get("avg_importance", 0) or 0)
    if avg_imp < 0.5:
        score -= 20
    elif avg_imp < 0.7:
        score -= 10
    
    # Penalize many never-accessed memories
    total = int(stats.get("total_memories", 1) or 1)
    never_accessed = int(stats.get("never_accessed", 0) or 0)
    if total > 0:
        unused_ratio = never_accessed / total
        if unused_ratio > 0.3:
            score -= 20
        elif unused_ratio > 0.1:
            score -= 10
    
    # Penalize many low-importance memories
    low_imp = int(stats.get("low_importance", 0) or 0)
    if total > 0:
        low_ratio = low_imp / total
        if low_ratio > 0.2:
            score -= 15
    
    # Penalize many contradictions
    contradictions = len(report.get("potential_contradictions", []))
    if contradictions > 10:
        score -= 15
    elif contradictions > 5:
        score -= 5
    
    return max(0, min(100, score))
