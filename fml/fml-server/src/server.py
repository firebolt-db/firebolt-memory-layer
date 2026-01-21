#!/usr/bin/env python3
"""FML MCP Server - Main entry point."""

import logging
from mcp.server.fastmcp import FastMCP

from src.tools.working_memory import register_working_memory_tools
from src.tools.longterm_memory import register_longterm_memory_tools
from src.tools.context import register_context_tools
from src.tools.stats import register_stats_tools
from src.tools.quality import register_quality_tools

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("fml-server")

# Create FastMCP server instance
mcp = FastMCP(
    name="firebolt-memory-layer",
    instructions="""
FML (Firebolt Memory Layer) provides intelligent memory management for LLMs.

Available tools:
- init_session: Start or resume a memory session
- add_to_working_memory: Add items to current session's working memory
- get_working_memory: Retrieve current working memory state
- update_working_memory_item: Update item properties (pinned, relevance)
- clear_working_memory: Clear session working memory
- store_memory: Store content in long-term memory with auto-classification
- recall_memories: Search long-term memory with semantic similarity
- update_memory: Update existing long-term memory
- forget_memory: Delete a memory (soft delete by default)
- get_relevant_context: Smart context assembly from all memory sources
- checkpoint_working_memory: Promote working memory to long-term storage
- get_fml_stats: Get server statistics and metrics for monitoring
- get_recent_calls: Get recent API calls for a service
- get_memory_analytics: Get detailed memory analytics and distribution
- memory_quality_report: Generate memory health report
- find_memory_contradictions: Find potentially outdated/contradictory memories
- supersede_memory: Mark old memory as replaced by newer one
- apply_memory_decay: Reduce importance of unused memories
- run_daily_maintenance: Run backup, decay, and quality checks
""",
)


def setup_server():
    """Register all tools with the server."""
    logger.info("Registering MCP tools...")

    register_working_memory_tools(mcp)
    logger.info("  ✓ Working memory tools registered")

    register_longterm_memory_tools(mcp)
    logger.info("  ✓ Long-term memory tools registered")

    register_context_tools(mcp)
    logger.info("  ✓ Context tools registered")

    register_stats_tools(mcp)
    logger.info("  ✓ Stats/monitoring tools registered")

    register_quality_tools(mcp)
    logger.info("  ✓ Quality/maintenance tools registered")

    logger.info("All tools registered successfully!")


# Initialize on import
setup_server()

if __name__ == "__main__":
    # Run with stdio transport for MCP clients
    mcp.run()
