"""
MCP Server - fastmcp Implementation
Experiment #5: MCP Framework Comparison
"""
import json
from fastmcp import FastMCP

# --- Mock data ---
MOCK_RESULTS = [
    {"id": "01HY0000000000000000000001", "title": "项羽", "score": 0.95, "type": "concept"},
    {"id": "01HY0000000000000000000003", "title": "鸿门宴", "score": 0.87, "type": "concept"},
]

# --- Server setup (3 lines total) ---
mcp = FastMCP("stratum-search-fastmcp")


@mcp.tool()
def stratum_search(query: str, mode: str = "exact") -> dict:
    """Search Stratum knowledge base for relevant nodes.

    Args:
        query: Search query string
        mode: Search mode - exact, semantic, or meta
    """
    if not query:
        raise ValueError("query is required")

    return {
        "results": MOCK_RESULTS,
        "query": query,
        "mode": mode,
        "total": len(MOCK_RESULTS),
    }


if __name__ == "__main__":
    mcp.run()
