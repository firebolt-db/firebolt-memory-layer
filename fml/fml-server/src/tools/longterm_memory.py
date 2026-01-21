"""Long-term memory MCP tools."""

import json
import traceback
import uuid
from typing import List, Optional
from mcp.server.fastmcp import FastMCP

from src.db.client import db
from src.llm.embeddings import embedding_service
from src.llm.ollama import ollama_service
from src.memory.taxonomy import validate_subtype
from src.metrics import log_tool_error


def register_longterm_memory_tools(mcp: FastMCP):
    """Register long-term memory tools with the MCP server."""

    @mcp.tool()
    async def store_memory(
        user_id: str,
        content: str,
        memory_category: Optional[str] = None,
        memory_subtype: Optional[str] = None,
        importance: float = 0.5,
        entities: Optional[str] = None,
        event_time: Optional[str] = None,
        metadata: Optional[str] = None,
        source_session: Optional[str] = None
    ) -> str:
        """
        Store a memory in long-term storage with auto-classification.

        Args:
            user_id: User who owns this memory
            content: The content to store
            memory_category: Category ('episodic', 'semantic', 'procedural', 'preference')
                            If not provided, will be auto-classified using local LLM
            memory_subtype: Subtype within category (auto-classified if not provided)
            importance: Importance score 0.0 to 1.0 (default: 0.5)
            entities: Comma-separated entities (e.g., 'table:users,database:prod_db')
            event_time: ISO timestamp for when the event occurred (for episodic memories)
            metadata: JSON string with additional metadata
            source_session: Session ID that created this memory

        Returns:
            JSON with memory_id, classification, and extracted entities
        """
        try:
            return await _store_memory_impl(
                user_id, content, memory_category, memory_subtype,
                importance, entities, event_time, metadata, source_session
            )
        except Exception as e:
            log_tool_error(
                tool_name="store_memory",
                error_message=str(e),
                user_id=user_id,
                error_type=type(e).__name__,
                input_preview=content[:200] if content else None,
                stack_trace=traceback.format_exc()
            )
            raise  # Re-raise so MCP returns the error to user

    async def _store_memory_impl(
        user_id: str,
        content: str,
        memory_category: Optional[str],
        memory_subtype: Optional[str],
        importance: float,
        entities: Optional[str],
        event_time: Optional[str],
        metadata: Optional[str],
        source_session: Optional[str]
    ) -> str:
        """Internal implementation of store_memory."""
        memory_id = str(uuid.uuid4())

        # Parse entities if provided as string
        entity_list = []
        if entities:
            entity_list = [e.strip() for e in entities.split(",") if e.strip()]

        # Auto-classify if category/subtype not provided
        if not memory_category or not memory_subtype:
            try:
                classification = ollama_service.classify_memory(content)
                memory_category = memory_category or classification.memory_category
                memory_subtype = memory_subtype or classification.memory_subtype

                # Use LLM-suggested importance if default
                if importance == 0.5:
                    importance = classification.importance

                # Use LLM-extracted entities if none provided
                if not entity_list:
                    entity_list = classification.entities
            except Exception as e:
                # Fallback to defaults if LLM fails
                memory_category = memory_category or "semantic"
                memory_subtype = memory_subtype or "domain"

        # Validate taxonomy
        if not validate_subtype(memory_category, memory_subtype):
            return json.dumps({
                "error": f"Invalid subtype '{memory_subtype}' for category '{memory_category}'"
            })

        # Extract additional entities if list is still empty
        if not entity_list:
            try:
                entity_list = ollama_service.extract_entities(content)
            except Exception:
                entity_list = []

        # Generate summary for long content (> 50 tokens) using OpenAI
        summary = None
        content_tokens = embedding_service.count_tokens(content)
        if content_tokens > 50:
            try:
                summary = ollama_service.summarize(content, max_words=50)
            except Exception:
                summary = None

        # Generate hypothetical questions for better semantic search using OpenAI
        hypothetical_questions = []
        try:
            hypothetical_questions = ollama_service.generate_hypothetical_questions(content)
        except Exception:
            hypothetical_questions = []

        # Create augmented text for embedding (content + questions for better retrieval)
        if hypothetical_questions:
            augmented_text = content + "\n\nQuestions this answers: " + " ".join(hypothetical_questions)
        else:
            augmented_text = content

        # Generate embedding from augmented text
        embedding = embedding_service.generate(augmented_text)

        # Check for similar existing memories to avoid duplicates
        similar = await _find_similar_memories(user_id, embedding, threshold=0.95)

        if similar:
            # Very similar memory exists - update it instead
            existing_id = similar[0]["memory_id"]
            db.execute("""
                UPDATE long_term_memories
                SET content = ?,
                    summary = ?,
                    embedding = ?,
                    importance = GREATEST(importance, ?),
                    access_count = access_count + 1,
                    updated_at = CURRENT_TIMESTAMP(),
                    last_accessed = CURRENT_TIMESTAMP()
                WHERE memory_id = ?
            """, (content, summary, embedding, importance, existing_id))

            return json.dumps({
                "memory_id": existing_id,
                "action": "updated_existing",
                "memory_category": memory_category,
                "memory_subtype": memory_subtype,
                "entities": entity_list,
                "summary": summary,
                "content_tokens": content_tokens,
                "similar_memory": similar[0]
            })

        # Insert new memory
        db.execute("""
            INSERT INTO long_term_memories (
                memory_id, user_id, memory_category, memory_subtype,
                content, summary, embedding, entities, importance,
                event_time, metadata, is_temporal, source_session, source_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            memory_id, user_id, memory_category, memory_subtype,
            content, summary, embedding, entity_list, importance,
            event_time, metadata, event_time is not None,
            source_session, "conversation"
        ))

        return json.dumps({
            "memory_id": memory_id,
            "action": "created_new",
            "memory_category": memory_category,
            "memory_subtype": memory_subtype,
            "entities": entity_list,
            "importance": importance,
            "summary": summary,
            "content_tokens": content_tokens,
            "hypothetical_questions": hypothetical_questions
        })

    @mcp.tool()
    async def recall_memories(
        user_id: str,
        query: str,
        memory_categories: Optional[str] = None,
        memory_subtypes: Optional[str] = None,
        entities: Optional[str] = None,
        limit: int = 10,
        min_similarity: float = 0.2,
        include_related: bool = False
    ) -> str:
        """
        Recall relevant memories using semantic search.

        Args:
            user_id: User whose memories to search
            query: Natural language query for semantic search
            memory_categories: Comma-separated categories to filter (e.g., 'episodic,semantic')
            memory_subtypes: Comma-separated subtypes to filter (e.g., 'decision,entity')
            entities: Comma-separated entities for exact matching (e.g., 'table:users')
            limit: Maximum number of memories to return (default: 10)
            min_similarity: Minimum similarity threshold (default: 0.2)
            include_related: Include related memories for each result (chunking). Default: False

        Returns:
            JSON with matching memories and retrieval statistics
        """
        # Generate query embedding
        query_embedding = embedding_service.generate(query)
        
        # Format embedding as literal for vector_search TVF (required for Firebolt 4.28)
        embedding_literal = _format_embedding_literal(query_embedding)

        # Build filter conditions for post-filtering after vector search
        conditions = ["user_id = ?", "deleted_at IS NULL"]
        params: List = [user_id]

        if memory_categories:
            categories = [c.strip() for c in memory_categories.split(",")]
            placeholders = ",".join(["?" for _ in categories])
            conditions.append(f"memory_category IN ({placeholders})")
            params.extend(categories)

        if memory_subtypes:
            subtypes = [s.strip() for s in memory_subtypes.split(",")]
            placeholders = ",".join(["?" for _ in subtypes])
            conditions.append(f"memory_subtype IN ({placeholders})")
            params.extend(subtypes)

        where_clause = " AND ".join(conditions)

        # Check if table has any data first (vector_search fails on empty tables)
        count_result = db.execute("SELECT COUNT(*) FROM long_term_memories WHERE user_id = ? AND deleted_at IS NULL", (user_id,))
        if not count_result or count_result[0][0] == 0:
            return json.dumps({
                "memories": [],
                "total_returned": 0,
                "query_tokens": embedding_service.count_tokens(query),
                "retrieval_breakdown": {"by_category": {}, "by_subtype": {}, "entity_matches": 0}
            })
        
        # Use vector_search TVF with HNSW index (positional params for v4.28)
        # TVF returns rows directly from the table (filtered by ANN search)
        # VECTOR_COSINE_SIMILARITY returns 1.0 for identical vectors
        # Fetch more candidates from index to allow for post-filtering
        top_k = limit * 3
        results = db.execute(f"""
            SELECT
                memory_id,
                content,
                summary,
                memory_category,
                memory_subtype,
                entities,
                importance,
                access_count,
                created_at,
                metadata,
                VECTOR_COSINE_SIMILARITY(embedding, {embedding_literal}) AS similarity
            FROM vector_search(
                INDEX idx_memories_embedding,
                {embedding_literal},
                {top_k},
                64
            )
            WHERE {where_clause}
            ORDER BY similarity DESC, importance DESC
            LIMIT ?
        """, (*params, limit * 2))  # Fetch extra for filtering

        # Filter by similarity threshold and entity matching
        entity_filter = []
        if entities:
            entity_filter = [e.strip() for e in entities.split(",")]

        memories = []
        for row in results:
            # Indices: 0=memory_id, 1=content, 2=summary, 3=category, 4=subtype,
            #          5=entities, 6=importance, 7=access_count, 8=created_at, 9=metadata, 10=similarity
            similarity = row[10] if row[10] is not None else 0.0

            if similarity < min_similarity:
                continue

            memory_entities = row[5] if row[5] else []

            # Entity boost: increase effective similarity for entity matches
            entity_boost = 1.0
            if entity_filter and memory_entities:
                matches = len(set(entity_filter) & set(memory_entities))
                if matches > 0:
                    entity_boost = 1.0 + (0.2 * matches)

            effective_similarity = min(1.0, similarity * entity_boost)

            memories.append({
                "memory_id": row[0],
                "content": row[1],
                "summary": row[2],
                "memory_category": row[3],
                "memory_subtype": row[4],
                "entities": memory_entities,
                "importance": row[6],
                "access_count": row[7],
                "created_at": str(row[8]) if row[8] else None,
                "metadata": row[9],
                "similarity": round(similarity, 4),
                "effective_similarity": round(effective_similarity, 4)
            })

            if len(memories) >= limit:
                break

        # Sort by effective similarity
        memories.sort(key=lambda x: x["effective_similarity"], reverse=True)

        # Update access counts for returned memories
        if memories:
            for mem in memories:
                db.execute("""
                    UPDATE long_term_memories
                    SET access_count = access_count + 1,
                        last_accessed = CURRENT_TIMESTAMP()
                    WHERE memory_id = ?
                """, (mem["memory_id"],))

        # Build retrieval breakdown
        breakdown = {
            "by_category": {},
            "by_subtype": {},
            "entity_matches": 0
        }

        for mem in memories:
            cat = mem["memory_category"]
            sub = mem["memory_subtype"]
            breakdown["by_category"][cat] = breakdown["by_category"].get(cat, 0) + 1
            breakdown["by_subtype"][sub] = breakdown["by_subtype"].get(sub, 0) + 1
            if entity_filter and mem["entities"]:
                if set(entity_filter) & set(mem["entities"]):
                    breakdown["entity_matches"] += 1

        # Include related memories if requested (chunking)
        if include_related and memories:
            seen_ids = {m["memory_id"] for m in memories}
            
            for mem in memories:
                related = db.execute("""
                    SELECT 
                        r.target_id, r.relationship, r.strength,
                        m.content, m.memory_category, m.memory_subtype
                    FROM memory_relationships r
                    JOIN long_term_memories m ON r.target_id = m.memory_id
                    WHERE r.source_id = ? AND r.user_id = ?
                      AND m.deleted_at IS NULL
                    ORDER BY r.strength DESC
                    LIMIT 3
                """, (mem["memory_id"], user_id))
                
                related_memories = []
                for row in related:
                    if row[0] not in seen_ids:  # Avoid duplicates
                        related_memories.append({
                            "memory_id": row[0],
                            "relationship": row[1],
                            "strength": row[2],
                            "content": row[3],
                            "memory_category": row[4],
                            "memory_subtype": row[5]
                        })
                        seen_ids.add(row[0])
                
                mem["related_memories"] = related_memories
            
            breakdown["related_memories_included"] = sum(
                len(m.get("related_memories", [])) for m in memories
            )

        return json.dumps({
            "memories": memories,
            "total_returned": len(memories),
            "query_tokens": embedding_service.count_tokens(query),
            "retrieval_breakdown": breakdown
        })

    @mcp.tool()
    async def update_memory(
        memory_id: str,
        user_id: str,
        content: Optional[str] = None,
        importance: Optional[float] = None,
        entities: Optional[str] = None,
        metadata: Optional[str] = None
    ) -> str:
        """
        Update an existing memory.

        Args:
            memory_id: The memory to update
            user_id: User who owns the memory (for authorization)
            content: New content (will regenerate embedding if changed)
            importance: New importance score
            entities: New comma-separated entities
            metadata: New metadata JSON string

        Returns:
            JSON with success status
        """
        # Verify ownership
        existing = db.execute(
            "SELECT user_id FROM long_term_memories WHERE memory_id = ? AND deleted_at IS NULL",
            (memory_id,)
        )

        if not existing:
            return json.dumps({"error": f"Memory not found: {memory_id}"})

        if existing[0][0] != user_id:
            return json.dumps({"error": "Unauthorized: memory belongs to different user"})

        updates = []
        params = []
        re_embedded = False

        if content is not None:
            updates.append("content = ?")
            params.append(content)
            # Regenerate embedding
            embedding = embedding_service.generate(content)
            updates.append("embedding = ?")
            params.append(embedding)
            re_embedded = True

        if importance is not None:
            updates.append("importance = ?")
            params.append(importance)

        if entities is not None:
            entity_list = [e.strip() for e in entities.split(",") if e.strip()]
            updates.append("entities = ?")
            params.append(entity_list)

        if metadata is not None:
            updates.append("metadata = ?")
            params.append(metadata)

        if not updates:
            return json.dumps({"error": "No updates provided"})

        updates.append("updated_at = CURRENT_TIMESTAMP()")
        params.extend([memory_id, user_id])

        db.execute(f"""
            UPDATE long_term_memories
            SET {", ".join(updates)}
            WHERE memory_id = ? AND user_id = ?
        """, tuple(params))

        return json.dumps({
            "success": True,
            "memory_id": memory_id,
            "re_embedded": re_embedded
        })

    @mcp.tool()
    async def forget_memory(
        memory_id: str,
        user_id: str,
        hard_delete: bool = False
    ) -> str:
        """
        Delete a memory (soft delete by default for GDPR compliance).

        Args:
            memory_id: The memory to delete
            user_id: User who owns the memory (for authorization)
            hard_delete: If True, permanently delete. If False, soft delete.

        Returns:
            JSON with success status
        """
        # Verify ownership
        existing = db.execute(
            "SELECT user_id FROM long_term_memories WHERE memory_id = ?",
            (memory_id,)
        )

        if not existing:
            return json.dumps({"error": f"Memory not found: {memory_id}"})

        if existing[0][0] != user_id:
            return json.dumps({"error": "Unauthorized: memory belongs to different user"})

        if hard_delete:
            db.execute(
                "DELETE FROM long_term_memories WHERE memory_id = ? AND user_id = ?",
                (memory_id, user_id)
            )
        else:
            db.execute("""
                UPDATE long_term_memories
                SET deleted_at = CURRENT_TIMESTAMP()
                WHERE memory_id = ? AND user_id = ?
            """, (memory_id, user_id))

        return json.dumps({
            "success": True,
            "memory_id": memory_id,
            "hard_deleted": hard_delete
        })

    @mcp.tool()
    async def forget_all_user_memories(
        user_id: str,
        confirmation: str
    ) -> str:
        """
        Delete all memories for a user (GDPR right to be forgotten).

        Args:
            user_id: User whose memories to delete
            confirmation: Must be "CONFIRM_DELETE_ALL" to proceed

        Returns:
            JSON with number of memories deleted
        """
        if confirmation != "CONFIRM_DELETE_ALL":
            return json.dumps({
                "error": "Confirmation required. Set confirmation to 'CONFIRM_DELETE_ALL'"
            })

        # Count memories
        count_result = db.execute(
            "SELECT COUNT(*) FROM long_term_memories WHERE user_id = ?",
            (user_id,)
        )
        memory_count = count_result[0][0] if count_result else 0

        # Count sessions
        session_result = db.execute(
            "SELECT COUNT(*) FROM session_contexts WHERE user_id = ?",
            (user_id,)
        )
        session_count = session_result[0][0] if session_result else 0

        # Delete all user data (including relationships)
        db.execute("DELETE FROM memory_access_log WHERE user_id = ?", (user_id,))
        db.execute("DELETE FROM memory_relationships WHERE user_id = ?", (user_id,))
        db.execute("DELETE FROM working_memory_items WHERE user_id = ?", (user_id,))
        db.execute("DELETE FROM long_term_memories WHERE user_id = ?", (user_id,))
        db.execute("DELETE FROM session_contexts WHERE user_id = ?", (user_id,))

        return json.dumps({
            "success": True,
            "memories_deleted": memory_count,
            "sessions_deleted": session_count,
            "user_id": user_id
        })

    # =========================================================================
    # MEMORY RELATIONSHIP TOOLS (Chunking)
    # =========================================================================

    @mcp.tool()
    async def link_memories(
        source_id: str,
        target_id: str,
        user_id: str,
        relationship: str = "related_to",
        strength: float = 1.0,
        context: Optional[str] = None,
        bidirectional: bool = True
    ) -> str:
        """
        Create a relationship between two memories (chunking).

        Supports the cognitive "Chunking" principle - grouping related items together
        for better recall. When one memory is retrieved, related memories can be
        pulled in for richer context.

        Args:
            source_id: The memory creating the relationship
            target_id: The memory being linked to
            user_id: User who owns both memories (for authorization)
            relationship: Type of relationship:
                - 'related_to': General association (default)
                - 'part_of': Target is a component/chunk of source
                - 'depends_on': Source requires target for context
                - 'contradicts': Memories have conflicting information
                - 'updates': Source is an update/correction of target
            strength: Relationship strength 0.0-1.0 (default: 1.0)
            context: Optional explanation of why these are related
            bidirectional: Create reverse link too (default: True)

        Returns:
            JSON with relationship details
        """
        # Verify both memories exist and belong to user
        source = db.execute(
            "SELECT memory_id, content FROM long_term_memories WHERE memory_id = ? AND user_id = ? AND deleted_at IS NULL",
            (source_id, user_id)
        )
        target = db.execute(
            "SELECT memory_id, content FROM long_term_memories WHERE memory_id = ? AND user_id = ? AND deleted_at IS NULL",
            (target_id, user_id)
        )

        if not source:
            return json.dumps({"error": f"Source memory not found: {source_id}"})
        if not target:
            return json.dumps({"error": f"Target memory not found: {target_id}"})

        # Validate relationship type
        valid_relationships = ["related_to", "part_of", "depends_on", "contradicts", "updates"]
        if relationship not in valid_relationships:
            return json.dumps({
                "error": f"Invalid relationship type: {relationship}",
                "valid_types": valid_relationships
            })

        # Check if relationship already exists
        existing = db.execute("""
            SELECT relationship_id FROM memory_relationships
            WHERE source_id = ? AND target_id = ? AND user_id = ?
        """, (source_id, target_id, user_id))

        if existing:
            # Update existing relationship
            db.execute("""
                UPDATE memory_relationships
                SET relationship = ?, strength = ?, context = ?
                WHERE source_id = ? AND target_id = ? AND user_id = ?
            """, (relationship, strength, context, source_id, target_id, user_id))
            action = "updated"
        else:
            # Create new relationship
            rel_id = str(uuid.uuid4())
            db.execute("""
                INSERT INTO memory_relationships (
                    relationship_id, source_id, target_id, user_id,
                    relationship, strength, context
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (rel_id, source_id, target_id, user_id, relationship, strength, context))
            action = "created"

        # Create bidirectional link if requested
        if bidirectional and relationship in ["related_to", "contradicts"]:
            reverse_existing = db.execute("""
                SELECT relationship_id FROM memory_relationships
                WHERE source_id = ? AND target_id = ? AND user_id = ?
            """, (target_id, source_id, user_id))

            if not reverse_existing:
                rev_id = str(uuid.uuid4())
                db.execute("""
                    INSERT INTO memory_relationships (
                        relationship_id, source_id, target_id, user_id,
                        relationship, strength, context
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (rev_id, target_id, source_id, user_id, relationship, strength, context))

        return json.dumps({
            "success": True,
            "action": action,
            "source": {
                "id": source_id,
                "content_preview": source[0][1][:80] + "..." if len(source[0][1]) > 80 else source[0][1]
            },
            "target": {
                "id": target_id,
                "content_preview": target[0][1][:80] + "..." if len(target[0][1]) > 80 else target[0][1]
            },
            "relationship": relationship,
            "strength": strength,
            "bidirectional": bidirectional and relationship in ["related_to", "contradicts"]
        })

    @mcp.tool()
    async def unlink_memories(
        source_id: str,
        target_id: str,
        user_id: str,
        bidirectional: bool = True
    ) -> str:
        """
        Remove a relationship between two memories.

        Args:
            source_id: The source memory of the relationship
            target_id: The target memory of the relationship
            user_id: User who owns the memories (for authorization)
            bidirectional: Also remove the reverse link (default: True)

        Returns:
            JSON with success status
        """
        # Delete the relationship
        db.execute("""
            DELETE FROM memory_relationships
            WHERE source_id = ? AND target_id = ? AND user_id = ?
        """, (source_id, target_id, user_id))

        if bidirectional:
            db.execute("""
                DELETE FROM memory_relationships
                WHERE source_id = ? AND target_id = ? AND user_id = ?
            """, (target_id, source_id, user_id))

        return json.dumps({
            "success": True,
            "unlinked": {
                "source_id": source_id,
                "target_id": target_id
            },
            "bidirectional": bidirectional
        })

    @mcp.tool()
    async def get_related_memories(
        memory_id: str,
        user_id: str,
        relationship_types: Optional[str] = None,
        include_reverse: bool = True,
        limit: int = 10
    ) -> str:
        """
        Get all memories related to a given memory.

        Retrieves the "chunk" of related memories for richer context during recall.
        This supports the cognitive Chunking principle.

        Args:
            memory_id: The memory to find relations for
            user_id: User who owns the memory (for authorization)
            relationship_types: Comma-separated relationship types to filter
                               (e.g., 'related_to,part_of'). None = all types.
            include_reverse: Include memories that link TO this memory (default: True)
            limit: Maximum related memories to return (default: 10)

        Returns:
            JSON with related memories and relationship details
        """
        # Verify memory exists
        memory = db.execute(
            "SELECT memory_id, content, memory_category FROM long_term_memories WHERE memory_id = ? AND user_id = ? AND deleted_at IS NULL",
            (memory_id, user_id)
        )

        if not memory:
            return json.dumps({"error": f"Memory not found: {memory_id}"})

        # Build query for outgoing relationships
        conditions = ["r.source_id = ?", "r.user_id = ?"]
        params: List = [memory_id, user_id]

        if relationship_types:
            types = [t.strip() for t in relationship_types.split(",")]
            placeholders = ",".join(["?" for _ in types])
            conditions.append(f"r.relationship IN ({placeholders})")
            params.extend(types)

        where_clause = " AND ".join(conditions)

        # Get outgoing relationships (this memory -> others)
        outgoing = db.execute(f"""
            SELECT 
                r.target_id, r.relationship, r.strength, r.context,
                m.content, m.memory_category, m.memory_subtype, m.importance
            FROM memory_relationships r
            JOIN long_term_memories m ON r.target_id = m.memory_id
            WHERE {where_clause}
              AND m.deleted_at IS NULL
            ORDER BY r.strength DESC
            LIMIT ?
        """, (*params, limit))

        related = []
        for row in outgoing:
            related.append({
                "memory_id": row[0],
                "relationship": row[1],
                "direction": "outgoing",
                "strength": row[2],
                "context": row[3],
                "content": row[4],
                "memory_category": row[5],
                "memory_subtype": row[6],
                "importance": row[7]
            })

        # Get incoming relationships (others -> this memory)
        if include_reverse:
            conditions[0] = "r.target_id = ?"
            params[0] = memory_id
            where_clause = " AND ".join(conditions)

            incoming = db.execute(f"""
                SELECT 
                    r.source_id, r.relationship, r.strength, r.context,
                    m.content, m.memory_category, m.memory_subtype, m.importance
                FROM memory_relationships r
                JOIN long_term_memories m ON r.source_id = m.memory_id
                WHERE {where_clause}
                  AND m.deleted_at IS NULL
                ORDER BY r.strength DESC
                LIMIT ?
            """, (*params, limit))

            for row in incoming:
                # Avoid duplicates from bidirectional links
                if not any(r["memory_id"] == row[0] for r in related):
                    related.append({
                        "memory_id": row[0],
                        "relationship": row[1],
                        "direction": "incoming",
                        "strength": row[2],
                        "context": row[3],
                        "content": row[4],
                        "memory_category": row[5],
                        "memory_subtype": row[6],
                        "importance": row[7]
                    })

        # Sort by strength and limit
        related.sort(key=lambda x: x["strength"], reverse=True)
        related = related[:limit]

        return json.dumps({
            "memory_id": memory_id,
            "memory_content": memory[0][1][:100] + "..." if len(memory[0][1]) > 100 else memory[0][1],
            "memory_category": memory[0][2],
            "related_count": len(related),
            "related_memories": related
        })

    @mcp.tool()
    async def auto_link_similar(
        memory_id: str,
        user_id: str,
        similarity_threshold: float = 0.75,
        max_links: int = 5
    ) -> str:
        """
        Automatically link a memory to similar memories.

        Uses vector similarity to find related memories and creates
        'related_to' relationships automatically. Useful for building
        memory chunks without manual curation.

        Args:
            memory_id: The memory to find similar memories for
            user_id: User who owns the memory
            similarity_threshold: Minimum similarity to create link (default: 0.75)
            max_links: Maximum number of links to create (default: 5)

        Returns:
            JSON with created links
        """
        # Get the memory and its content for re-embedding
        memory = db.execute(
            "SELECT memory_id, content, memory_category FROM long_term_memories WHERE memory_id = ? AND user_id = ? AND deleted_at IS NULL",
            (memory_id, user_id)
        )

        if not memory:
            return json.dumps({"error": f"Memory not found: {memory_id}"})

        content = memory[0][1]
        category = memory[0][2]
        
        # Generate fresh embedding (DB returns string format, so regenerate)
        embedding = embedding_service.generate(content)
        embedding_literal = _format_embedding_literal(embedding)

        # Find similar memories (same category for better relevance)
        similar = db.execute(f"""
            SELECT 
                memory_id, content,
                VECTOR_COSINE_SIMILARITY(embedding, {embedding_literal}) AS similarity
            FROM long_term_memories
            WHERE user_id = ?
              AND memory_id != ?
              AND memory_category = ?
              AND deleted_at IS NULL
            ORDER BY similarity DESC
            LIMIT ?
        """, (user_id, memory_id, category, max_links * 2))

        # Create links for memories above threshold
        links_created = []
        for row in similar:
            sim_id, sim_content, similarity = row
            
            if similarity is None or similarity < similarity_threshold:
                continue

            if len(links_created) >= max_links:
                break

            # Check if link already exists
            existing = db.execute("""
                SELECT 1 FROM memory_relationships
                WHERE source_id = ? AND target_id = ? AND user_id = ?
            """, (memory_id, sim_id, user_id))

            if not existing:
                rel_id = str(uuid.uuid4())
                db.execute("""
                    INSERT INTO memory_relationships (
                        relationship_id, source_id, target_id, user_id,
                        relationship, strength, context
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    rel_id, memory_id, sim_id, user_id,
                    "related_to", round(similarity, 4),
                    f"Auto-linked by similarity ({round(similarity, 2)})"
                ))

                # Bidirectional
                rev_id = str(uuid.uuid4())
                db.execute("""
                    INSERT INTO memory_relationships (
                        relationship_id, source_id, target_id, user_id,
                        relationship, strength, context
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    rev_id, sim_id, memory_id, user_id,
                    "related_to", round(similarity, 4),
                    f"Auto-linked by similarity ({round(similarity, 2)})"
                ))

                links_created.append({
                    "target_id": sim_id,
                    "content_preview": sim_content[:80] + "..." if len(sim_content) > 80 else sim_content,
                    "similarity": round(similarity, 4)
                })

        return json.dumps({
            "success": True,
            "memory_id": memory_id,
            "links_created": len(links_created),
            "links": links_created,
            "threshold_used": similarity_threshold
        })


def _format_embedding_literal(embedding: List[float]) -> str:
    """Format embedding as SQL literal for vector_search TVF (required for Firebolt 4.28)."""
    values = ", ".join(str(v) for v in embedding)
    return f"[{values}]::ARRAY(DOUBLE)"


async def _find_similar_memories(
    user_id: str,
    embedding: List[float],
    threshold: float = 0.95
) -> List[dict]:
    """Find memories with very high similarity (for deduplication).
    
    Uses vector_search() TVF with HNSW index for fast approximate nearest neighbor search.
    """
    # Format embedding as literal (required for Firebolt 4.28 - no parameterized vectors)
    embedding_literal = _format_embedding_literal(embedding)
    
    # Check if table has any data first (vector_search fails on empty tables)
    count_result = db.execute("SELECT COUNT(*) FROM long_term_memories WHERE user_id = ? AND deleted_at IS NULL", (user_id,))
    if not count_result or count_result[0][0] == 0:
        return []
    
    # Use vector_search TVF with the HNSW index (positional params for v4.28)
    # TVF returns rows directly from the table (filtered by ANN search)
    query = f"""
        SELECT
            memory_id,
            content,
            VECTOR_COSINE_SIMILARITY(embedding, {embedding_literal}) AS similarity
        FROM vector_search(
            INDEX idx_memories_embedding,
            {embedding_literal},
            10,
            64
        )
        WHERE user_id = ? AND deleted_at IS NULL
        ORDER BY similarity DESC
        LIMIT 3
    """
    
    results = db.execute(query, (user_id,))

    similar = []
    for row in results:
        if row[2] and row[2] >= threshold:
            similar.append({
                "memory_id": row[0],
                "content": row[1][:100] + "..." if len(row[1]) > 100 else row[1],
                "similarity": round(row[2], 4)
            })

    return similar
