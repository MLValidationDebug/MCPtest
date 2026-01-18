"""MCP Server implementation with tools."""

import anyio
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from mcp_server.tools import calculator, notes_manager, get_current_time, list_timezones


# Define available tools
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
                    "description": "The arithmetic operation to perform"
                },
                "a": {
                    "type": "number",
                    "description": "First number"
                },
                "b": {
                    "type": "number",
                    "description": "Second number"
                }
            },
            "required": ["operation", "a", "b"]
        }
    ),
    Tool(
        name="create_note",
        description="Create a new note with title and content",
        inputSchema={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Note title"
                },
                "content": {
                    "type": "string",
                    "description": "Note content"
                }
            },
            "required": ["title", "content"]
        }
    ),
    Tool(
        name="get_note",
        description="Retrieve a note by its ID",
        inputSchema={
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "Note ID (e.g., 'note-1')"
                }
            },
            "required": ["id"]
        }
    ),
    Tool(
        name="list_notes",
        description="List all stored notes",
        inputSchema={
            "type": "object",
            "properties": {}
        }
    ),
    Tool(
        name="delete_note",
        description="Delete a note by its ID",
        inputSchema={
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "Note ID to delete"
                }
            },
            "required": ["id"]
        }
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
                    "default": "UTC"
                }
            }
        }
    ),
    Tool(
        name="list_timezones",
        description="List common available timezones",
        inputSchema={
            "type": "object",
            "properties": {}
        }
    )
]


# Create MCP server
app = Server("mcp-demo-server")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    try:
        result = None
        
        if name == "calculator":
            result = calculator(
                operation=arguments["operation"],
                a=arguments["a"],
                b=arguments["b"]
            )
        
        elif name == "create_note":
            result = notes_manager.create_note(
                title=arguments["title"],
                content=arguments["content"]
            )
        
        elif name == "get_note":
            result = notes_manager.get_note(
                note_id=arguments["id"]
            )
        
        elif name == "list_notes":
            result = notes_manager.list_notes()
        
        elif name == "delete_note":
            result = notes_manager.delete_note(
                note_id=arguments["id"]
            )
        
        elif name == "get_current_time":
            timezone = arguments.get("timezone", "UTC")
            result = get_current_time(timezone=timezone)
        
        elif name == "list_timezones":
            result = list_timezones()
        
        else:
            raise ValueError(f"Unknown tool: {name}")
        
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
    import sys
    # Ensure stderr messages appear
    print("MCP Server starting...", file=sys.stderr, flush=True)
    
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
    import sys
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
