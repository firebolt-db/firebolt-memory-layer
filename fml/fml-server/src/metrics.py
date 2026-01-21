"""Metrics collection for FML monitoring dashboard."""

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from collections import deque
import threading


@dataclass
class CallMetric:
    """Single API call metric."""
    timestamp: datetime
    service: str  # 'ollama', 'firebolt', 'embedding'
    operation: str  # 'classify', 'query', 'embed', etc.
    latency_ms: float
    tokens_in: int = 0
    tokens_out: int = 0
    success: bool = True
    error: Optional[str] = None


def _persist_metric_to_db(metric: CallMetric) -> None:
    """Persist a metric to the database (best effort, non-blocking)."""
    try:
        # Import here to avoid circular dependency
        from src.db.client import db
        
        metric_id = str(uuid.uuid4())
        error_escaped = metric.error.replace("'", "''") if metric.error else None
        
        query = f"""
            INSERT INTO service_metrics 
            (metric_id, service, operation, latency_ms, success, error_msg, tokens_in, tokens_out)
            VALUES (
                '{metric_id}', 
                '{metric.service}', 
                '{metric.operation}', 
                {metric.latency_ms}, 
                {'TRUE' if metric.success else 'FALSE'}, 
                {f"'{error_escaped}'" if error_escaped else 'NULL'},
                {metric.tokens_in or 'NULL'}, 
                {metric.tokens_out or 'NULL'}
            )
        """
        db.execute(query)
    except Exception:
        # Don't let metrics persistence failures affect the main app
        pass


class MetricsCollector:
    """Thread-safe metrics collector for FML."""

    _instance: Optional["MetricsCollector"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "MetricsCollector":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # Keep last 1000 calls for each service
        self.max_history = 1000
        self._calls: Dict[str, deque] = {
            "ollama": deque(maxlen=self.max_history),
            "firebolt": deque(maxlen=self.max_history),
            "embedding": deque(maxlen=self.max_history),
        }

        # Aggregate counters (never reset)
        self._totals: Dict[str, Dict[str, int]] = {
            "ollama": {"calls": 0, "errors": 0, "tokens_in": 0, "tokens_out": 0},
            "firebolt": {"calls": 0, "errors": 0, "rows_returned": 0},
            "embedding": {"calls": 0, "errors": 0, "tokens": 0},
        }

        self._start_time = datetime.now()
        self._initialized = True

    def record_call(
        self,
        service: str,
        operation: str,
        latency_ms: float,
        tokens_in: int = 0,
        tokens_out: int = 0,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """Record an API call metric."""
        # Skip recording metrics about metrics queries to avoid infinite loop
        if service == "firebolt" and operation in ("metrics_query", "other"):
            return
            
        metric = CallMetric(
            timestamp=datetime.now(),
            service=service,
            operation=operation,
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            success=success,
            error=error,
        )

        with self._lock:
            if service in self._calls:
                self._calls[service].append(metric)

            # Update totals
            if service in self._totals:
                self._totals[service]["calls"] += 1
                if not success:
                    self._totals[service]["errors"] += 1
                if service == "ollama":
                    self._totals[service]["tokens_in"] += tokens_in
                    self._totals[service]["tokens_out"] += tokens_out
                elif service == "embedding":
                    self._totals[service]["tokens"] += tokens_in

        # Persist to database for cross-process visibility
        # Only persist ollama and embedding (not firebolt - that would be recursive)
        if service in ("ollama", "embedding"):
            threading.Thread(target=_persist_metric_to_db, args=(metric,), daemon=True).start()

    def get_stats(self, time_window_minutes: int = 60) -> Dict:
        """Get aggregated statistics."""
        cutoff = datetime.now().timestamp() - (time_window_minutes * 60)

        with self._lock:
            stats = {
                "uptime_seconds": (datetime.now() - self._start_time).total_seconds(),
                "collection_start": self._start_time.isoformat(),
                "time_window_minutes": time_window_minutes,
                "services": {},
            }

            for service, calls in self._calls.items():
                # Filter to time window
                recent = [c for c in calls if c.timestamp.timestamp() > cutoff]

                if recent:
                    latencies = [c.latency_ms for c in recent]
                    avg_latency = sum(latencies) / len(latencies)
                    p95_latency = sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) >= 20 else max(latencies)

                    # Group by operation
                    by_operation = {}
                    for call in recent:
                        if call.operation not in by_operation:
                            by_operation[call.operation] = {"count": 0, "errors": 0, "total_latency": 0}
                        by_operation[call.operation]["count"] += 1
                        by_operation[call.operation]["total_latency"] += call.latency_ms
                        if not call.success:
                            by_operation[call.operation]["errors"] += 1

                    # Calculate avg for each operation
                    for op, data in by_operation.items():
                        data["avg_latency_ms"] = data["total_latency"] / data["count"]
                        del data["total_latency"]

                    stats["services"][service] = {
                        "calls_in_window": len(recent),
                        "errors_in_window": sum(1 for c in recent if not c.success),
                        "avg_latency_ms": round(avg_latency, 2),
                        "p95_latency_ms": round(p95_latency, 2),
                        "by_operation": by_operation,
                        "total_calls": self._totals[service]["calls"],
                        "total_errors": self._totals[service]["errors"],
                    }

                    # Service-specific metrics
                    if service == "ollama":
                        stats["services"][service]["tokens_in_window"] = sum(c.tokens_in for c in recent)
                        stats["services"][service]["tokens_out_window"] = sum(c.tokens_out for c in recent)
                        stats["services"][service]["total_tokens_in"] = self._totals[service]["tokens_in"]
                        stats["services"][service]["total_tokens_out"] = self._totals[service]["tokens_out"]
                else:
                    stats["services"][service] = {
                        "calls_in_window": 0,
                        "total_calls": self._totals[service]["calls"],
                        "total_errors": self._totals[service]["errors"],
                    }

            return stats

    def get_recent_calls(self, service: str, limit: int = 50) -> List[Dict]:
        """Get recent calls for a service."""
        with self._lock:
            if service not in self._calls:
                return []
            calls = list(self._calls[service])[-limit:]
            return [
                {
                    "timestamp": c.timestamp.isoformat(),
                    "operation": c.operation,
                    "latency_ms": round(c.latency_ms, 2),
                    "tokens_in": c.tokens_in,
                    "tokens_out": c.tokens_out,
                    "success": c.success,
                    "error": c.error,
                }
                for c in reversed(calls)
            ]

    def reset(self) -> None:
        """Reset all metrics (for testing)."""
        with self._lock:
            for service in self._calls:
                self._calls[service].clear()
                self._totals[service] = {k: 0 for k in self._totals[service]}
            self._start_time = datetime.now()


# Singleton instance
metrics = MetricsCollector()


def log_tool_error(
    tool_name: str,
    error_message: str,
    user_id: Optional[str] = None,
    error_type: Optional[str] = None,
    input_preview: Optional[str] = None,
    stack_trace: Optional[str] = None
) -> None:
    """Log an MCP tool error for review and debugging."""
    try:
        from src.db.client import db
        
        error_id = str(uuid.uuid4())
        
        # Escape strings for SQL
        def escape(s: Optional[str]) -> str:
            if s is None:
                return "NULL"
            escaped = s.replace("'", "''")[:1000]  # Limit length
            return f"'{escaped}'"
        
        query = f"""
            INSERT INTO tool_error_log 
            (error_id, tool_name, user_id, error_type, error_message, input_preview, stack_trace)
            VALUES (
                '{error_id}',
                {escape(tool_name)},
                {escape(user_id)},
                {escape(error_type)},
                {escape(error_message)},
                {escape(input_preview)},
                {escape(stack_trace)}
            )
        """
        db.execute(query)
    except Exception:
        # Don't let error logging failures affect the main app
        pass


# Context manager for timing calls
class timed_call:
    """Context manager to time and record API calls."""

    def __init__(
        self,
        service: str,
        operation: str,
        tokens_in: int = 0,
    ):
        self.service = service
        self.operation = operation
        self.tokens_in = tokens_in
        self.tokens_out = 0
        self.start_time = None

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        latency_ms = (time.perf_counter() - self.start_time) * 1000
        success = exc_type is None
        error = str(exc_val) if exc_val else None

        metrics.record_call(
            service=self.service,
            operation=self.operation,
            latency_ms=latency_ms,
            tokens_in=self.tokens_in,
            tokens_out=self.tokens_out,
            success=success,
            error=error,
        )

        return False  # Don't suppress exceptions
