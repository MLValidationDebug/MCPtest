"""HTTP-based MCP server (streamable HTTP transport).

Runs as an ASGI app (Starlette) so the MCP gateway can connect over HTTP
using `type: "streamable-http"` with the server URL.

Tools mirror the existing stdio server: calculator, notes, time utilities.
"""

import json
import os
import sys
from pathlib import Path

from starlette.applications import Starlette
from starlette.routing import Mount

from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import Tool, TextContent

# Make sure we can import the shared tool implementations
sys.path.insert(0, str(Path(__file__).parent.parent))
from mcp_server.tools import calculator, notes_manager, get_current_time, list_timezones  # noqa: E402


app = Server("mcp-http-server")


TOOLS = [
    Tool(
        name="calculator",
        description="Perform basic arithmetic operations (add, subtract, multiply, divide)",
        inputSchema={
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["add", "subtract", "multiply", "divide"],
                    "description": "The arithmetic operation to perform",
                },
                "a": {"type": "number", "description": "First number"},
                "b": {"type": "number", "description": "Second number"},
            },
            "required": ["operation", "a", "b"],
        },
    ),
    Tool(
        name="create_note",
        description="Create a new note with title and content",
        inputSchema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Note title"},
                "content": {"type": "string", "description": "Note content"},
            },
            "required": ["title", "content"],
        },
    ),
    Tool(
        name="get_note",
        description="Retrieve a note by its ID",
        inputSchema={
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Note ID (e.g., 'note-1')"},
            },
            "required": ["id"],
        },
    ),
    Tool(
        name="list_notes",
        description="List all stored notes",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="delete_note",
        description="Delete a note by its ID",
        inputSchema={
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Note ID to delete"},
            },
            "required": ["id"],
        },
    ),
    Tool(
        name="get_current_time",
        description="Get current time in a specific timezone",
        inputSchema={
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "Timezone name (e.g., 'UTC', 'America/New_York', 'Asia/Tokyo'). Defaults to 'UTC'",
                    "default": "UTC",
                }
            },
        },
    ),
    Tool(
        name="list_timezones",
        description="List common available timezones",
        inputSchema={"type": "object", "properties": {}},
    ),
]


@app.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        result = None

        if name == "calculator":
            result = calculator(
                operation=arguments["operation"],
                a=arguments["a"],
                b=arguments["b"],
            )
        elif name == "create_note":
            result = notes_manager.create_note(
                title=arguments["title"],
                content=arguments["content"],
            )
        elif name == "get_note":
            result = notes_manager.get_note(note_id=arguments["id"])
        elif name == "list_notes":
            result = notes_manager.list_notes()
        elif name == "delete_note":
            result = notes_manager.delete_note(note_id=arguments["id"])
        elif name == "get_current_time":
            timezone = arguments.get("timezone", "UTC")
            result = get_current_time(timezone=timezone)
        elif name == "list_timezones":
            result = list_timezones()
        else:
            raise ValueError(f"Unknown tool: {name}")

        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as e:  # Keep server alive, return error text
        return [TextContent(type="text", text=f"Error: {str(e)}")]


# Streamable HTTP session manager wraps the MCP server into an ASGI app
session_manager = StreamableHTTPSessionManager(
    app=app,
    json_response=False,  # use SSE streaming responses (recommended for MCP)
    stateless=False,      # keep sessions so tools/list isn't re-negotiated each call
)


async def lifespan(_):
    async with session_manager.run():
        yield


starlette_app = Starlette(
    routes=[Mount("/", app=session_manager.handle_request)],
    lifespan=lifespan,
)


def main():
    import uvicorn

    host = os.environ.get("MCP_HTTP_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_HTTP_PORT", "8001"))

    print(f"Starting HTTP MCP server on http://{host}:{port}", file=sys.stderr, flush=True)
    uvicorn.run(starlette_app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    import os
    main()
