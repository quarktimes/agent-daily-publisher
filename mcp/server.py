"""
MCP Server — Expose Daily Publisher state via Model Context Protocol.

This MCP server allows Claude Code (and other MCP clients) to query
the daily publisher system: what was published today, what sessions
were captured, pipeline status, etc.

This demonstrates the MCP protocol integration — a key skill for
modern agent development.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

# Try to import MCP SDK; fall back gracefully if not installed
try:
    from mcp.server import Server, NotificationOptions
    from mcp.server.models import InitializationOptions
    import mcp.server.stdio
    import mcp.types as types
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False


DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


class DailyPublisherTools:
    """Tool implementations for the MCP server."""

    @staticmethod
    def get_today_summary(date_str: str | None = None) -> dict:
        """Get the publish summary for a given date."""
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")

        published_file = os.path.join(DATA_DIR, "published", f"{date_str}.json")
        if os.path.exists(published_file):
            with open(published_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"date": date_str, "status": "no_data"}

    @staticmethod
    def get_sessions(date_str: str | None = None) -> list[dict]:
        """Get captured sessions for a date."""
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")

        sessions_file = os.path.join(DATA_DIR, "sessions", f"{date_str}.jsonl")
        sessions = []
        if os.path.exists(sessions_file):
            with open(sessions_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            sessions.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        return sessions

    @staticmethod
    def get_pipeline_status() -> dict:
        """Get latest pipeline run status."""
        traces_dir = os.path.join(DATA_DIR, "traces")
        if not os.path.exists(traces_dir):
            return {"status": "no_runs_yet"}

        today = datetime.now().strftime("%Y-%m-%d")
        pipeline_file = os.path.join(traces_dir, f"{today}_pipeline_runs.jsonl")
        if os.path.exists(pipeline_file):
            with open(pipeline_file, "r", encoding="utf-8") as f:
                runs = [json.loads(line) for line in f if line.strip()]
            if runs:
                return runs[-1]
        return {"status": "no_run_today"}

    @staticmethod
    def get_recent_articles(limit: int = 5) -> list[dict]:
        """Get most recently published articles."""
        articles_dir = os.path.join(DATA_DIR, "articles")
        if not os.path.exists(articles_dir):
            return []

        files = sorted(Path(articles_dir).iterdir(), key=os.path.getmtime, reverse=True)
        articles = []
        for f in files[:limit]:
            if f.suffix == ".md":
                with open(f, "r", encoding="utf-8") as fh:
                    content = fh.read()
                articles.append({
                    "filename": f.name,
                    "size": len(content),
                    "preview": content[:200] if content else "",
                })
        return articles


if MCP_AVAILABLE:
    server = Server("daily-publisher")

    @server.list_tools()
    async def handle_list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="get_today_summary",
                description="Get the publishing summary for today or a specific date",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "date": {"type": "string", "description": "Date in YYYY-MM-DD format (default: today)"},
                    },
                },
            ),
            types.Tool(
                name="get_recent_sessions",
                description="Get recent Claude Code sessions captured for publishing",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "date": {"type": "string", "description": "Date in YYYY-MM-DD format (default: today)"},
                    },
                },
            ),
            types.Tool(
                name="get_pipeline_status",
                description="Get the latest pipeline run status",
                inputSchema={"type": "object", "properties": {}},
            ),
            types.Tool(
                name="get_recent_articles",
                description="List recently generated articles",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "number", "description": "Number of articles to return (default: 5)"},
                    },
                },
            ),
        ]

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
        tools = DailyPublisherTools()
        arg = arguments or {}

        if name == "get_today_summary":
            result = tools.get_today_summary(arg.get("date"))
        elif name == "get_recent_sessions":
            result = tools.get_sessions(arg.get("date"))
        elif name == "get_pipeline_status":
            result = tools.get_pipeline_status()
        elif name == "get_recent_articles":
            result = tools.get_recent_articles(arg.get("limit", 5))
        else:
            raise ValueError(f"Unknown tool: {name}")

        return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    async def run():
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="daily-publisher",
                    server_version="0.1.0",
                ),
            )

    def main():
        import asyncio
        asyncio.run(run())

else:
    print("MCP SDK not available. Install with: pip install mcp")
    print("Running in standalone mode — MCP server not started.")

    def main():
        print("Agent Daily Publisher — MCP Server")
        print("  Start: python -m mcp.server")
        print("  Install MCP SDK: pip install mcp")
        print("")
        print("Available tools:")
        tools = DailyPublisherTools()
        print(f"  get_today_summary() -> {json.dumps(tools.get_today_summary(), ensure_ascii=False)[:100]}")
        print(f"  get_recent_sessions() -> {len(tools.get_sessions())} sessions")
        print(f"  get_pipeline_status() -> {json.dumps(tools.get_pipeline_status(), ensure_ascii=False)[:100]}")


if __name__ == "__main__":
    main()
