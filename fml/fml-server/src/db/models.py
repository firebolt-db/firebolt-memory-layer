"""Pydantic models for database entities."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class SessionContext(BaseModel):
    """Working memory session."""
    session_id: str
    user_id: str
    org_id: Optional[str] = None
    total_tokens: int = 0
    max_tokens: int = 8000
    created_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    config: Optional[str] = None


class WorkingMemoryItem(BaseModel):
    """Item in working memory."""
    item_id: str
    session_id: str
    user_id: str
    content_type: str  # 'message', 'task_state', 'scratchpad', 'retrieved_memory'
    content: str
    token_count: int
    relevance_score: float = 1.0
    pinned: bool = False
    sequence_num: int
    created_at: Optional[datetime] = None
    last_accessed: Optional[datetime] = None


class LongTermMemory(BaseModel):
    """Long-term memory entry."""
    memory_id: str
    user_id: str
    org_id: Optional[str] = None
    memory_category: str  # 'episodic', 'semantic', 'procedural', 'preference'
    memory_subtype: str
    content: str
    summary: Optional[str] = None
    embedding: Optional[List[float]] = None
    entities: List[str] = Field(default_factory=list)
    metadata: Optional[str] = None
    event_time: Optional[datetime] = None
    is_temporal: bool = False
    importance: float = 0.5
    access_count: int = 0
    decay_factor: float = 1.0
    # NOTE: related_memories removed due to Firebolt Core bug with NULL arrays
    supersedes: Optional[str] = None
    source_session: Optional[str] = None
    source_type: Optional[str] = None
    confidence: float = 1.0
    created_at: Optional[datetime] = None
    last_accessed: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None


class MemoryAccessLog(BaseModel):
    """Log entry for memory access."""
    access_id: str
    memory_id: str
    session_id: str
    user_id: str
    query_text: Optional[str] = None
    similarity_score: Optional[float] = None
    was_useful: Optional[bool] = None
    was_used: Optional[bool] = None
    accessed_at: Optional[datetime] = None
