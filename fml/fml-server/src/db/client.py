"""Firebolt database client - supports both Cloud and Core (local)."""

import json
import requests
import threading
from contextlib import contextmanager
from typing import Any, List, Optional, Tuple
from firebolt.db import connect
from firebolt.client.auth import ClientCredentials

from src.config import config
from src.metrics import timed_call


class FireboltClient:
    """Singleton Firebolt database client - supports Cloud and Core."""

    _instance: Optional["FireboltClient"] = None
    _lock = threading.Lock()  # Mutex for serializing Firebolt Core requests

    def __new__(cls) -> "FireboltClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # Check if using Firebolt Core (local)
        self.use_core = config.firebolt.use_core
        self.core_url = config.firebolt.core_url

        if self.use_core:
            print(f"Using Firebolt Core at {self.core_url}")
            self.database = config.firebolt.database
        else:
            print(f"Using Firebolt Cloud: {config.firebolt.account_name}")
            self.auth = ClientCredentials(
                client_id=config.firebolt.client_id,
                client_secret=config.firebolt.client_secret,
            )
            self.account_name = config.firebolt.account_name
            self.database = config.firebolt.database
            self.engine = config.firebolt.engine

        self._initialized = True

    def _get_connection(self):
        """Create a new database connection (Cloud only)."""
        if self.use_core:
            raise RuntimeError("Cannot use connection for Firebolt Core - use execute() instead")
        return connect(
            auth=self.auth,
            account_name=self.account_name,
            database=self.database,
            engine_name=self.engine,
        )

    @contextmanager
    def get_cursor(self):
        """Context manager for database cursor (Cloud only)."""
        if self.use_core:
            raise RuntimeError("Cannot use cursor for Firebolt Core - use execute() instead")
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
        finally:
            cursor.close()
            conn.close()

    def execute(self, query: str, params: Tuple = ()) -> List[Tuple[Any, ...]]:
        """Execute a query and return results."""
        # Determine operation type from query
        query_upper = query.strip().upper()
        if query_upper.startswith("SELECT"):
            operation = "select"
        elif query_upper.startswith("INSERT"):
            operation = "insert"
        elif query_upper.startswith("UPDATE"):
            operation = "update"
        elif query_upper.startswith("DELETE"):
            operation = "delete"
        else:
            operation = "other"

        with timed_call("firebolt", operation):
            if self.use_core:
                # Serialize all Firebolt Core requests to avoid transaction conflicts
                with self._lock:
                    return self._execute_core(query, params)
            else:
                return self._execute_cloud(query, params)

    def _execute_cloud(self, query: str, params: Tuple = ()) -> List[Tuple[Any, ...]]:
        """Execute query on Firebolt Cloud."""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            try:
                return cursor.fetchall()
            except Exception:
                return []

    def _execute_core(self, query: str, params: Tuple = ()) -> List[Tuple[Any, ...]]:
        """Execute query on Firebolt Core (local)."""
        # Substitute parameters into query (simple substitution)
        final_query = query
        if params:
            for param in params:
                if isinstance(param, str):
                    # Escape single quotes by doubling them (SQL standard)
                    escaped = param.replace("'", "''")
                    final_query = final_query.replace('?', f"'{escaped}'", 1)
                elif param is None:
                    final_query = final_query.replace('?', 'NULL', 1)
                elif isinstance(param, bool):
                    final_query = final_query.replace('?', str(param).upper(), 1)
                elif isinstance(param, (list, tuple)):
                    # Array parameter - format for Firebolt SQL
                    if len(param) == 0:
                        array_str = "ARRAY[]"
                    elif all(isinstance(x, (int, float)) for x in param):
                        # Numeric array (e.g., embeddings)
                        array_str = "[" + ", ".join(str(x) for x in param) + "]"
                    else:
                        # String array - escape single quotes
                        escaped = [str(x).replace("'", "''") for x in param]
                        array_str = "ARRAY[" + ", ".join(f"'{x}'" for x in escaped) + "]"
                    final_query = final_query.replace('?', array_str, 1)
                else:
                    final_query = final_query.replace('?', str(param), 1)

        # Build request with vector search settings enabled
        # Use root endpoint (not /query) for better compatibility
        url = self.core_url
        url_params = ["output_format=TabSeparatedWithNamesAndTypes"]
        if self.database:
            url_params.append(f"database={self.database}")
        # Enable advanced features for vector search
        url_params.append("advanced_mode=1")
        url_params.append("enable_vector_search_index_creation=1")
        url_params.append("enable_vector_search_tvf=1")
        url += "?" + "&".join(url_params)

        response = requests.post(
            url,
            headers={
                "Content-Type": "text/plain",
                "Connection": "close"  # Disable keep-alive to prevent transaction leaks
            },
            data=final_query,
            timeout=60
        )
        response.close()  # Ensure connection is closed

        # Parse response from Firebolt Core
        text = response.text.strip()
        if not text:
            return []

        # Check for JSON error response
        if text.startswith('{'):
            try:
                error_data = json.loads(text)
                if "errors" in error_data and error_data["errors"]:
                    error_msg = error_data["errors"][0].get("description", "Unknown error")
                    raise RuntimeError(f"Firebolt Core error: {error_msg}")
            except json.JSONDecodeError:
                pass  # Not JSON, continue with TSV parsing

        lines = text.split('\n')
        if len(lines) < 2:
            return []  # No data rows

        # Get column types from second line
        type_line = lines[1] if len(lines) > 1 else ""
        col_types = type_line.split('\t') if type_line else []

        # Skip header line and type line, parse data rows
        data_lines = lines[2:] if len(lines) > 2 else []
        results = []
        for line in data_lines:
            if line.strip():
                values = line.split('\t')
                typed_values = []
                for i, val in enumerate(values):
                    typed_val = self._convert_core_value(val, col_types[i] if i < len(col_types) else "")
                    typed_values.append(typed_val)
                results.append(tuple(typed_values))

        return results

    def _convert_core_value(self, value: str, col_type: str) -> Any:
        """Convert string value from Firebolt Core TSV to appropriate Python type."""
        if value == '' or value == '\\N':
            return None

        col_type_lower = col_type.lower()

        # Integer types
        if 'int' in col_type_lower or 'bigint' in col_type_lower:
            try:
                return int(value)
            except ValueError:
                return value

        # Float types
        if 'real' in col_type_lower or 'double' in col_type_lower or 'float' in col_type_lower:
            try:
                return float(value)
            except ValueError:
                return value

        # Boolean
        if 'bool' in col_type_lower:
            return value.lower() in ('true', '1', 't')

        # Array types - Firebolt Core returns arrays as JSON-like strings
        if 'array' in col_type_lower:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value

        # Default to string
        return value

    def execute_many(self, query: str, params_list: List[Tuple]) -> None:
        """Execute a query with multiple parameter sets."""
        for params in params_list:
            self.execute(query, params)

    def execute_script(self, script: str) -> None:
        """Execute a SQL script with multiple statements."""
        statements = [s.strip() for s in script.split(';') if s.strip()]
        for stmt in statements:
            if stmt and not stmt.startswith('--'):
                self.execute(stmt)


# Singleton instance
db = FireboltClient()
