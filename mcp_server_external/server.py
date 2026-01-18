"""External MCP Server implementation with additional tools."""

import json
import sys
import platform
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent


# Define available tools
TOOLS = [
    Tool(
        name="system_info",
        description="Get basic system and runtime information",
        inputSchema={
            "type": "object",
            "properties": {}
        }
    )
]


# Create MCP server
app = Server("mcp-external-server")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    try:
        if name != "system_info":
            raise ValueError(f"Unknown tool: {name}")

        result = {
            "os": platform.system(),
            "os_version": platform.version(),
            "python_version": platform.python_version(),
            "machine": platform.machine(),
            "timestamp_utc": datetime.now(timezone.utc).isoformat()
        }

        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]

    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Error: {str(e)}"
        )]


async def run_server():
    """Run the MCP server."""
    print("External MCP Server starting...", file=sys.stderr, flush=True)

    try:
        async with stdio_server() as streams:
            await app.run(streams[0], streams[1], app.create_initialization_options())
    except Exception as e:
        print(f"Server error: {e}", file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
        raise


def main():
    """Entry point for the server."""
    import anyio
    try:
        anyio.run(run_server)
    except KeyboardInterrupt:
        print("Server stopped", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
