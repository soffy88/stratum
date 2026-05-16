"""
MCP Server - Anthropic Official SDK Implementation
Experiment #5: MCP Framework Comparison
"""
import asyncio
import json
import time
from typing import Any

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server

# --- Mock data ---
MOCK_RESULTS = [
    {"id": "01HY0000000000000000000001", "title": "项羽", "score": 0.95, "type": "concept"},
    {"id": "01HY0000000000000000000003", "title": "鸿门宴", "score": 0.87, "type": "concept"},
]

# --- Server setup ---
server = Server("stratum-search-anthropic-sdk")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="stratum.search",
            description="Search Stratum knowledge base for relevant nodes",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query string",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["exact", "semantic", "meta"],
                        "default": "exact",
                        "description": "Search mode",
                    },
                },
                "required": ["query"],
            },
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    if name != "stratum.search":
        raise ValueError(f"Unknown tool: {name}")

    query = arguments.get("query", "")
    mode = arguments.get("mode", "exact")

    if not query:
        raise ValueError("query is required")

    result = {
        "results": MOCK_RESULTS,
        "query": query,
        "mode": mode,
        "total": len(MOCK_RESULTS),
    }

    return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
