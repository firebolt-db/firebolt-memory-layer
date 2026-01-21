"""Smart context assembly MCP tool."""

import json
import uuid
from typing import Dict, List, Optional
from mcp.server.fastmcp import FastMCP

from src.db.client import db
from src.llm.embeddings import embedding_service
from src.llm.ollama import ollama_service
from src.memory.taxonomy import get_retrieval_weights


def register_context_tools(mcp: FastMCP):
    """Register context assembly tools with the MCP server."""

    @mcp.tool()
    async def get_relevant_context(
        session_id: str,
        user_id: str,
        query: str,
        token_budget: int,
        query_intent: Optional[str] = None,
        focus_entities: Optional[str] = None
    ) -> str:
        """
        Assemble optimal context from working + long-term memory.

        This is the primary "magic" tool that intelligently combines:
        - Working memory (current session context)
        - Episodic memory (past events, decisions)
        - Semantic memory (facts, entities, project knowledge)
        - Procedural memory (workflows, patterns)
        - Preference memory (user preferences, style)

        Args:
            session_id: Current session ID
            user_id: User ID for memory retrieval
            query: The query/task to find relevant context for
            token_budget: Maximum tokens for the assembled context
            query_intent: Intent hint ('how_to', 'what_happened', 'what_is', 'debug', 'general')
                         Auto-detected if not provided
            focus_entities: Comma-separated entities to boost (e.g., 'table:users,file:api.py')

        Returns:
            JSON with assembled context items, token usage, and retrieval stats
        """
        # Detect intent if not provided
        detected_intent = query_intent
        if not detected_intent:
            try:
                detected_intent = ollama_service.detect_query_intent(query)
            except Exception:
                detected_intent = "general"

        # Get retrieval weights for this intent
        weights = get_retrieval_weights(detected_intent)

        # Parse focus entities
        entity_filter = []
        if focus_entities:
            entity_filter = [e.strip() for e in focus_entities.split(",") if e.strip()]

        context_items = []
        total_tokens = 0

        # Phase 1: Get working memory items
        working_budget = int(token_budget * weights.get("working_memory", 0.35))
        working_items = await _get_working_memory_context(
            session_id, working_budget
        )

        for item in working_items:
            context_items.append({
                "source": "working_memory",
                "content": item["content"],
                "content_type": item["content_type"],
                "relevance_score": item["relevance_score"],
                "token_count": item["token_count"],
                "why_included": f"Recent {item['content_type']} from current session"
            })
            total_tokens += item["token_count"]

        # Phase 2: Get long-term memories
        remaining_budget = token_budget - total_tokens
        query_embedding = embedding_service.generate(query)

        # Collect candidates from all memory types
        ltm_candidates = []

        for weight_key, weight in weights.items():
            if weight_key == "working_memory":
                continue

            parts = weight_key.split(".")
            if len(parts) != 2:
                continue

            category, subtype = parts
            type_budget = int(remaining_budget * weight)

            if type_budget < 50:  # Skip if budget too small for meaningful content
                continue

            memories = await _get_memories_by_type(
                user_id, query_embedding, category, subtype,
                entity_filter, limit=5
            )

            for mem in memories:
                token_count = embedding_service.count_tokens(mem["content"])
                ltm_candidates.append({
                    "memory_id": mem["memory_id"],
                    "content": mem["content"],
                    "memory_category": category,
                    "memory_subtype": subtype,
                    "entities": mem.get("entities", []),
                    "token_count": token_count,
                    "similarity": mem["similarity"],
                    "importance": mem["importance"],
                    "weight": weight,
                    "score": mem["similarity"] * weight * (1 + mem["importance"])
                })

        # Entity boost: increase score for memories matching focus entities
        if entity_filter:
            for item in ltm_candidates:
                item_entities = item.get("entities") or []
                matches = len(set(entity_filter) & set(item_entities))
                if matches > 0:
                    item["score"] *= (1 + 0.3 * matches)  # 30% boost per match
                    item["entity_match"] = True

        # Sort by score and fill remaining budget
        ltm_candidates.sort(key=lambda x: x["score"], reverse=True)

        # Deduplicate by content similarity (avoid near-duplicate entries)
        seen_content_hashes = set()

        for item in ltm_candidates:
            if total_tokens + item["token_count"] > token_budget:
                continue

            # Simple dedup: check content hash
            content_hash = hash(item["content"][:200])
            if content_hash in seen_content_hashes:
                continue
            seen_content_hashes.add(content_hash)

            context_items.append({
                "source": "long_term",
                "memory_category": item["memory_category"],
                "memory_subtype": item["memory_subtype"],
                "content": item["content"],
                "relevance_score": round(item["score"], 3),
                "token_count": item["token_count"],
                "entities": item["entities"],
                "why_included": _generate_why_included(item)
            })
            total_tokens += item["token_count"]

            # Log access for analytics
            await _log_memory_access(
                item["memory_id"], session_id, user_id,
                query, item["similarity"]
            )

        # Build retrieval stats
        stats = _build_retrieval_stats(context_items, entity_filter)

        return json.dumps({
            "context_items": context_items,
            "total_tokens": total_tokens,
            "budget_used_pct": round(total_tokens / token_budget * 100, 2),
            "detected_intent": detected_intent,
            "retrieval_stats": stats
        })

    @mcp.tool()
    async def checkpoint_working_memory(
        session_id: str,
        user_id: str
    ) -> str:
        """
        Checkpoint working memory to long-term storage.

        Analyzes working memory items and promotes important ones to long-term memory.
        This should be called periodically or at conversation boundaries.

        Args:
            session_id: Session to checkpoint
            user_id: User ID for memory storage

        Returns:
            JSON with number of memories created/updated and tokens freed
        """
        # Get all working memory items
        items = db.execute("""
            SELECT item_id, content_type, content, token_count, relevance_score
            FROM working_memory_items
            WHERE session_id = ? AND pinned = FALSE
            ORDER BY sequence_num ASC
        """, (session_id,))

        if not items:
            return json.dumps({
                "memories_created": 0,
                "memories_updated": 0,
                "working_memory_tokens_freed": 0
            })

        memories_created = 0
        memories_updated = 0
        tokens_to_free = 0
        items_to_delete = []

        # Analyze each item for storage worthiness
        for item in items:
            item_id, content_type, content, token_count, relevance_score = item

            # Skip very short or low-relevance items
            if token_count < 20 or relevance_score < 0.3:
                continue

            # Skip system messages and retrieved memories (already stored)
            if content_type in ("system", "retrieved_memory"):
                continue

            # Classify and store
            try:
                classification = ollama_service.classify_memory(content)

                # Only store if importance is high enough
                if classification.importance < 0.4:
                    continue

                # Generate embedding
                embedding = embedding_service.generate(content)

                # Check for duplicates
                similar = db.execute("""
                    SELECT memory_id, VECTOR_COSINE_SIMILARITY(embedding, ?) AS sim
                    FROM long_term_memories
                    WHERE user_id = ? AND deleted_at IS NULL
                    ORDER BY sim DESC
                    LIMIT 1
                """, (embedding, user_id))

                if similar and similar[0][1] and similar[0][1] > 0.9:
                    # Update existing memory
                    db.execute("""
                        UPDATE long_term_memories
                        SET access_count = access_count + 1,
                            last_accessed = CURRENT_TIMESTAMP()
                        WHERE memory_id = ?
                    """, (similar[0][0],))
                    memories_updated += 1
                else:
                    # Create new memory
                    memory_id = str(uuid.uuid4())

                    db.execute("""
                        INSERT INTO long_term_memories (
                            memory_id, user_id, memory_category, memory_subtype,
                            content, embedding, entities, importance,
                            source_session, source_type
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        memory_id, user_id,
                        classification.memory_category,
                        classification.memory_subtype,
                        content, embedding,
                        classification.entities,
                        classification.importance,
                        session_id, "checkpoint"
                    ))
                    memories_created += 1

                # Mark for deletion from working memory
                items_to_delete.append(item_id)
                tokens_to_free += token_count

            except Exception as e:
                # Skip items that fail classification
                continue

        # Delete checkpointed items from working memory
        if items_to_delete:
            placeholders = ",".join(["?" for _ in items_to_delete])
            db.execute(f"""
                DELETE FROM working_memory_items
                WHERE item_id IN ({placeholders})
            """, tuple(items_to_delete))

            # Update session token count
            db.execute("""
                UPDATE session_contexts
                SET total_tokens = total_tokens - ?
                WHERE session_id = ?
            """, (tokens_to_free, session_id))

        return json.dumps({
            "memories_created": memories_created,
            "memories_updated": memories_updated,
            "working_memory_tokens_freed": tokens_to_free,
            "items_processed": len(items_to_delete)
        })


async def _get_working_memory_context(
    session_id: str,
    token_budget: int
) -> List[Dict]:
    """Get working memory items within budget."""
    items = db.execute("""
        SELECT item_id, content_type, content, token_count, relevance_score
        FROM working_memory_items
        WHERE session_id = ?
        ORDER BY pinned DESC, sequence_num DESC
    """, (session_id,))

    result = []
    used_tokens = 0

    for item in items:
        token_count = item[3]
        if used_tokens + token_count > token_budget:
            continue

        result.append({
            "item_id": item[0],
            "content_type": item[1],
            "content": item[2],
            "token_count": token_count,
            "relevance_score": item[4]
        })
        used_tokens += token_count

    return result


async def _get_memories_by_type(
    user_id: str,
    query_embedding: List[float],
    category: str,
    subtype: str,
    entity_filter: List[str],
    limit: int = 5
) -> List[Dict]:
    """Get memories of a specific type with vector similarity.
    
    Note: We explicitly select only needed columns to avoid Firebolt Core bug
    with NULL array columns (related_memories) that causes S3 file errors.
    """
    # Format embedding as literal for Firebolt 4.28
    emb_literal = "[" + ", ".join(str(v) for v in query_embedding) + "]::ARRAY(DOUBLE)"
    
    results = db.execute(f"""
        SELECT
            memory_id, content, entities, importance,
            VECTOR_COSINE_SIMILARITY(embedding, {emb_literal}) AS similarity
        FROM long_term_memories
        WHERE user_id = ?
          AND memory_category = ?
          AND memory_subtype = ?
          AND deleted_at IS NULL
        ORDER BY similarity DESC
        LIMIT ?
    """, (user_id, category, subtype, limit))

    memories = []
    for row in results:
        if row[4] is None or row[4] < 0.5:  # Skip low similarity
            continue

        memories.append({
            "memory_id": row[0],
            "content": row[1],
            "entities": row[2] if row[2] else [],
            "importance": row[3],
            "similarity": row[4]
        })

    return memories


def _generate_why_included(item: Dict) -> str:
    """Generate human-readable explanation for why item was included."""
    parts = []

    cat = item["memory_category"]
    sub = item["memory_subtype"]
    parts.append(f"{cat}.{sub} memory")

    if item.get("entity_match"):
        parts.append("entity match")

    score = item.get("score", 0)
    if score > 0.8:
        parts.append("highly relevant")
    elif score > 0.5:
        parts.append("relevant")

    return " | ".join(parts)


def _build_retrieval_stats(
    context_items: List[Dict],
    entity_filter: List[str]
) -> Dict:
    """Build retrieval statistics."""
    stats = {
        "working_memory_items": 0,
        "long_term_items": 0,
        "by_category": {},
        "by_subtype": {},
        "entity_boost_applied": bool(entity_filter)
    }

    for item in context_items:
        if item["source"] == "working_memory":
            stats["working_memory_items"] += 1
        else:
            stats["long_term_items"] += 1
            cat = item.get("memory_category", "unknown")
            sub = item.get("memory_subtype", "unknown")
            stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1
            stats["by_subtype"][sub] = stats["by_subtype"].get(sub, 0) + 1

    return stats


async def _log_memory_access(
    memory_id: str,
    session_id: str,
    user_id: str,
    query_text: str,
    similarity_score: float
) -> None:
    """Log memory access for analytics."""
    access_id = str(uuid.uuid4())

    try:
        db.execute("""
            INSERT INTO memory_access_log (
                access_id, memory_id, session_id, user_id,
                query_text, similarity_score
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (access_id, memory_id, session_id, user_id,
              query_text[:500], similarity_score))
    except Exception:
        # Don't fail if logging fails
        pass
