#!/usr/bin/env python3
"""HTTP API server for FML dashboard.

This provides a REST API for the dashboard to fetch stats,
since the MCP server uses stdio transport.

Run with: python -m src.http_api
"""

import json
import os
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from src.db.client import db
from src.metrics import metrics
from src.config import config

# Capture server start time and code file modification time for sync detection
_SERVER_START_TIME = datetime.now()
_CODE_FILE_PATH = os.path.abspath(__file__)
_CODE_MTIME = datetime.fromtimestamp(os.path.getmtime(_CODE_FILE_PATH))


class DashboardAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for dashboard API."""

    def send_json(self, data, status=200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        try:
            if path == '/api/stats':
                self.handle_stats(query)
            elif path.startswith('/api/calls/'):
                service = path.split('/')[-1]
                self.handle_calls(service, query)
            elif path == '/api/analytics':
                self.handle_analytics(query)
            elif path == '/api/config':
                self.handle_config()
            elif path == '/api/version':
                self.handle_version()
            elif path == '/api/health':
                self.send_json({"status": "ok"})
            else:
                self.send_json({"error": "Not found"}, 404)
        except Exception as e:
            self.send_json({"error": str(e)}, 500)

    def handle_stats(self, query):
        """Get FML stats."""
        time_window = int(query.get('window', [60])[0])
        
        # Get metrics from collector (local firebolt calls)
        service_stats = metrics.get_stats(time_window)
        
        # Augment with database metrics for ollama/embedding (cross-process)
        try:
            # Get ollama metrics from database - windowed stats
            ollama_window = db.execute(f"""
                SELECT 
                    COUNT(*) as cnt,
                    COALESCE(AVG(latency_ms), 0) as avg_lat,
                    COALESCE(SUM(tokens_in), 0) as tok_in,
                    COALESCE(SUM(tokens_out), 0) as tok_out,
                    SUM(CASE WHEN success = FALSE THEN 1 ELSE 0 END) as errs
                FROM service_metrics 
                WHERE service = 'ollama'
                AND recorded_at > NOW() - INTERVAL '{time_window} minutes'
            """)
            
            # Get ollama TOTAL counts (all time, no window filter)
            ollama_totals = db.execute("""
                SELECT 
                    COUNT(*) as total_cnt,
                    SUM(CASE WHEN success = FALSE THEN 1 ELSE 0 END) as total_errs
                FROM service_metrics 
                WHERE service = 'ollama'
            """)
            
            total_ollama_calls = int(ollama_totals[0][0]) if ollama_totals else 0
            total_ollama_errors = int(ollama_totals[0][1]) if ollama_totals and ollama_totals[0][1] else 0
            
            if ollama_window and int(ollama_window[0][0]) > 0:
                service_stats["services"]["ollama"] = {
                    "calls_in_window": int(ollama_window[0][0]),
                    "avg_latency_ms": round(float(ollama_window[0][1]), 2),
                    "tokens_in_window": int(ollama_window[0][2]) if ollama_window[0][2] else 0,
                    "tokens_out_window": int(ollama_window[0][3]) if ollama_window[0][3] else 0,
                    "errors_in_window": int(ollama_window[0][4]) if ollama_window[0][4] else 0,
                    "total_calls": total_ollama_calls,
                    "total_errors": total_ollama_errors,
                }
            elif total_ollama_calls > 0:
                # No recent calls but we have historical data
                service_stats["services"]["ollama"] = {
                    "calls_in_window": 0,
                    "avg_latency_ms": 0,
                    "tokens_in_window": 0,
                    "tokens_out_window": 0,
                    "errors_in_window": 0,
                    "total_calls": total_ollama_calls,
                    "total_errors": total_ollama_errors,
                }
                
            # Get embedding metrics from database - windowed stats
            embed_window = db.execute(f"""
                SELECT 
                    COUNT(*) as cnt,
                    COALESCE(AVG(latency_ms), 0) as avg_lat,
                    COALESCE(SUM(tokens_in), 0) as tok_in,
                    SUM(CASE WHEN success = FALSE THEN 1 ELSE 0 END) as errs
                FROM service_metrics 
                WHERE service = 'embedding'
                AND recorded_at > NOW() - INTERVAL '{time_window} minutes'
            """)
            
            # Get embedding TOTAL counts (all time, no window filter)
            embed_totals = db.execute("""
                SELECT 
                    COUNT(*) as total_cnt,
                    SUM(CASE WHEN success = FALSE THEN 1 ELSE 0 END) as total_errs
                FROM service_metrics 
                WHERE service = 'embedding'
            """)
            
            total_embed_calls = int(embed_totals[0][0]) if embed_totals else 0
            total_embed_errors = int(embed_totals[0][1]) if embed_totals and embed_totals[0][1] else 0
            
            if embed_window and int(embed_window[0][0]) > 0:
                service_stats["services"]["embedding"] = {
                    "calls_in_window": int(embed_window[0][0]),
                    "avg_latency_ms": round(float(embed_window[0][1]), 2),
                    "tokens_in_window": int(embed_window[0][2]) if embed_window[0][2] else 0,
                    "errors_in_window": int(embed_window[0][3]) if embed_window[0][3] else 0,
                    "total_calls": total_embed_calls,
                    "total_errors": total_embed_errors,
                }
            elif total_embed_calls > 0:
                # No recent calls but we have historical data
                service_stats["services"]["embedding"] = {
                    "calls_in_window": 0,
                    "avg_latency_ms": 0,
                    "tokens_in_window": 0,
                    "errors_in_window": 0,
                    "total_calls": total_embed_calls,
                    "total_errors": total_embed_errors,
                }
        except Exception as e:
            # If database query fails, stick with in-memory stats
            pass

        # Get memory counts from database
        try:
            ltm_result = db.execute(
                "SELECT COUNT(*) FROM long_term_memories WHERE deleted_at IS NULL"
            )
            ltm_count = ltm_result[0][0] if ltm_result else 0

            sessions_result = db.execute(
                "SELECT COUNT(*) FROM session_contexts"
            )
            session_count = sessions_result[0][0] if sessions_result else 0

            wm_result = db.execute(
                "SELECT COUNT(*) FROM working_memory_items"
            )
            wm_items = wm_result[0][0] if wm_result else 0

            tokens_result = db.execute(
                "SELECT COALESCE(SUM(token_count), 0) FROM working_memory_items"
            )
            wm_tokens = tokens_result[0][0] if tokens_result else 0

            access_result = db.execute(
                "SELECT COUNT(*) FROM memory_access_log"
            )
            access_log_count = access_result[0][0] if access_result else 0

            category_result = db.execute("""
                SELECT memory_category, COUNT(*) as cnt
                FROM long_term_memories
                WHERE deleted_at IS NULL
                GROUP BY memory_category
            """)
            by_category = {row[0]: row[1] for row in category_result}

            top_accessed = db.execute("""
                SELECT memory_id, memory_category, access_count, importance, content
                FROM long_term_memories
                WHERE deleted_at IS NULL
                ORDER BY access_count DESC
                LIMIT 5
            """)

            # Get storage sizes from SHOW TABLES
            # Include all FML tables for accurate total
            FML_TABLES = [
                'long_term_memories', 
                'working_memory_items', 
                'session_contexts', 
                'memory_access_log',
                'memory_relationships',  # Join table for memory linking
                'tool_error_log',        # Error tracking
                'service_metrics',       # Ollama/embedding metrics (if exists)
            ]
            storage_stats = {"total_compressed": 0, "total_uncompressed": 0, "tables": {}}
            try:
                tables_result = db.execute("SHOW TABLES")
                # SHOW TABLES columns (Firebolt Core):
                # 0=table_name, 1=table_type, 2=column_count, 3=primary_index, 4=create_statement,
                # 5=number_of_rows, 6=size_compressed, 7=size_uncompressed, 8=compression_ratio, 9=?
                for row in tables_result:
                    table_name = row[0]
                    if table_name in FML_TABLES:
                        row_count = int(row[5]) if row[5] else 0
                        compressed = row[6] if row[6] else "0 B"
                        uncompressed = row[7] if row[7] else "0 B"
                        
                        # Parse size strings like "75.70 KiB" to bytes
                        def parse_size(size_str):
                            if not size_str or size_str == "0.00 B":
                                return 0
                            parts = size_str.split()
                            if len(parts) != 2:
                                return 0
                            value = float(parts[0])
                            unit = parts[1].upper()
                            multipliers = {"B": 1, "KIB": 1024, "MIB": 1024**2, "GIB": 1024**3}
                            return int(value * multipliers.get(unit, 1))
                        
                        comp_bytes = parse_size(compressed)
                        uncomp_bytes = parse_size(uncompressed)
                        
                        storage_stats["tables"][table_name] = {
                            "rows": row_count,
                            "compressed": compressed,
                            "compressed_bytes": comp_bytes,
                            "uncompressed": uncompressed,
                            "uncompressed_bytes": uncomp_bytes,
                        }
                        storage_stats["total_compressed"] += comp_bytes
                        storage_stats["total_uncompressed"] += uncomp_bytes
            except Exception as e:
                storage_stats["error"] = str(e)

            # Format total sizes
            def format_size(bytes_val):
                if bytes_val < 1024:
                    return f"{bytes_val} B"
                elif bytes_val < 1024**2:
                    return f"{bytes_val/1024:.2f} KiB"
                elif bytes_val < 1024**3:
                    return f"{bytes_val/1024**2:.2f} MiB"
                else:
                    return f"{bytes_val/1024**3:.2f} GiB"

            storage_stats["total_compressed_formatted"] = format_size(storage_stats["total_compressed"])
            storage_stats["total_uncompressed_formatted"] = format_size(storage_stats["total_uncompressed"])

            memory_stats = {
                "long_term_memories": ltm_count,
                "active_sessions": session_count,
                "working_memory_items": wm_items,
                "working_memory_tokens": wm_tokens,
                "access_log_entries": access_log_count,
                "by_category": by_category,
                "top_accessed": [
                    {
                        "memory_id": row[0][:8] + "..." if row[0] else "",
                        "category": row[1],
                        "access_count": row[2],
                        "importance": row[3],
                        "content_preview": (row[4][:100] + "..." if len(row[4]) > 100 else row[4]) if row[4] else "",
                    }
                    for row in top_accessed
                ],
                "storage": storage_stats,
            }
        except Exception as e:
            memory_stats = {"error": str(e)}

        self.send_json({
            **service_stats,
            "memory": memory_stats,
        })

    def handle_calls(self, service, query):
        """Get recent calls for a service."""
        limit = int(query.get('limit', [50])[0])
        
        # First try to get from database (persisted across restarts)
        calls = []
        try:
            result = db.execute(f"""
                SELECT 
                    recorded_at,
                    operation,
                    latency_ms,
                    tokens_in,
                    tokens_out,
                    success,
                    error_msg
                FROM service_metrics
                WHERE service = '{service}'
                ORDER BY recorded_at DESC
                LIMIT {limit}
            """)
            
            calls = [
                {
                    "timestamp": str(row[0]),
                    "operation": row[1],
                    "latency_ms": round(float(row[2]), 2),
                    "tokens_in": int(row[3]) if row[3] else 0,
                    "tokens_out": int(row[4]) if row[4] else 0,
                    "success": row[5] if isinstance(row[5], bool) else str(row[5]).lower() == 'true',
                    "error": row[6],
                }
                for row in result
            ]
        except Exception:
            # Fall back to in-memory metrics
            calls = metrics.get_recent_calls(service, limit)
        
        self.send_json({
            "service": service,
            "call_count": len(calls),
            "calls": calls,
        })

    def handle_config(self):
        """Get FML configuration (brain location, etc)."""
        self.send_json({
            "brain_location": "local" if config.firebolt.use_core else "cloud",
            "firebolt": {
                "use_core": config.firebolt.use_core,
                "core_url": config.firebolt.core_url if config.firebolt.use_core else None,
                "account_name": config.firebolt.account_name if not config.firebolt.use_core else None,
                "database": config.firebolt.database,
            },
            "ollama": {
                "host": config.ollama.host,
                "model": config.ollama.model,
                "embedding_model": config.ollama.embedding_model,
            }
        })

    def handle_version(self):
        """Get server version info and detect code sync issues.
        
        Returns server start time, code modification time, and whether
        the server needs a restart to pick up code changes.
        """
        # Re-check file mtime in case it changed
        current_mtime = datetime.fromtimestamp(os.path.getmtime(_CODE_FILE_PATH))
        
        # Server needs restart if code was modified after server started
        needs_restart = current_mtime > _SERVER_START_TIME
        
        self.send_json({
            "server_start_time": _SERVER_START_TIME.isoformat(),
            "code_modified_time": current_mtime.isoformat(),
            "code_loaded_time": _CODE_MTIME.isoformat(),
            "needs_restart": needs_restart,
            "uptime_seconds": (datetime.now() - _SERVER_START_TIME).total_seconds(),
            "message": "Server is running stale code - restart required!" if needs_restart else "Server is up to date",
        })

    def handle_analytics(self, query):
        """Get memory analytics."""
        user_id = query.get('user_id', [None])[0]
        
        try:
            user_filter = ""
            params = ()
            if user_id:
                user_filter = "AND user_id = ?"
                params = (user_id,)

            subtype_result = db.execute(f"""
                SELECT memory_category, memory_subtype, COUNT(*) as cnt
                FROM long_term_memories
                WHERE deleted_at IS NULL {user_filter}
                GROUP BY memory_category, memory_subtype
                ORDER BY cnt DESC
            """, params)

            by_subtype = [
                {"category": row[0], "subtype": row[1], "count": row[2]}
                for row in subtype_result
            ]

            importance_result = db.execute(f"""
                SELECT
                    CASE
                        WHEN importance >= 0.8 THEN 'critical'
                        WHEN importance >= 0.6 THEN 'high'
                        WHEN importance >= 0.4 THEN 'medium'
                        ELSE 'low'
                    END as priority,
                    COUNT(*) as cnt
                FROM long_term_memories
                WHERE deleted_at IS NULL {user_filter}
                GROUP BY priority
            """, params)

            by_importance = {row[0]: row[1] for row in importance_result}

            self.send_json({
                "by_subtype": by_subtype,
                "by_importance": by_importance,
                "user_filter": user_id or "all",
            })
        except Exception as e:
            self.send_json({"error": str(e)}, 500)

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def run_server(port=8082):
    """Run the HTTP API server."""
    server = HTTPServer(('', port), DashboardAPIHandler)
    print(f"🔥 FML Dashboard API running on http://localhost:{port}")
    print(f"   Endpoints:")
    print(f"   - GET /api/stats")
    print(f"   - GET /api/calls/<service>")
    print(f"   - GET /api/analytics")
    print(f"   - GET /api/health")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
