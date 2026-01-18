"""MCP Gateway Server that aggregates tools from registered MCP servers."""

import json
import sys
from pathlib import Path
from typing import Dict, Tuple, List

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client
from mcp import ClientSession


class MCPGateway:
    """Gateway that aggregates tools from multiple MCP servers."""

    def __init__(self, registry_path: Path):
        self.registry_path = registry_path
        self.sessions: Dict[str, ClientSession] = {}
        self.stdio_contexts: Dict[str, any] = {}
        self.http_clients: Dict[str, any] = {}
        self.tools: List[Tool] = []
        self.tool_map: Dict[str, Tuple[str, str]] = {}

    def _load_registry(self) -> dict:
        if not self.registry_path.exists():
            raise FileNotFoundError(f"Registry file not found: {self.registry_path}")
        with self.registry_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    async def connect(self):
        registry = self._load_registry()
        servers = registry.get("servers", [])
        if not servers:
            raise ValueError("Registry has no servers configured")

        self.tools = []
        self.tool_map = {}
        self.sessions = {}
        self.stdio_contexts = {}
        self.http_clients = {}

        for server in servers:
            server_id = server.get("id")
            server_type = server.get("type", "stdio")
            if not server_id:
                raise ValueError("Registry server entry missing 'id'")
            headers = server.get("headers")
            base_dir = self.registry_path.parent

            if server_type == "stdio":
                command = server.get("command") or sys.executable
                if command == "python":
                    command = sys.executable

                args = server.get("args", [])
                resolved_args = []
                for arg in args:
                    arg_path = Path(arg)
                    if arg_path.exists() or (not arg_path.is_absolute() and (base_dir / arg_path).exists()):
                        resolved_args.append(str((base_dir / arg_path).resolve()))
                    else:
                        resolved_args.append(arg)

                server_params = StdioServerParameters(
                    command=command,
                    args=resolved_args,
                    env=server.get("env")
                )

                transport_context = stdio_client(server_params)
                read_stream, write_stream = await transport_context.__aenter__()

            elif server_type == "sse":
                url = server.get("url")
                if not url:
                    raise ValueError(f"Server '{server_id}' missing 'url' for SSE")
                transport_context = sse_client(url, headers=headers)
                read_stream, write_stream = await transport_context.__aenter__()

            elif server_type == "streamable-http":
                url = server.get("url")
                if not url:
                    raise ValueError(f"Server '{server_id}' missing 'url' for streamable-http")
                http_client = create_mcp_http_client(headers=headers)
                self.http_clients[server_id] = http_client
                transport_context = streamable_http_client(url, http_client=http_client)
                read_stream, write_stream, _ = await transport_context.__aenter__()

            else:
                raise ValueError(f"Unsupported server type: {server_type}")

            session = ClientSession(read_stream, write_stream)
            await session.__aenter__()
            await session.initialize()

            tools_result = await session.list_tools()
            for tool in tools_result.tools:
                namespaced_name = f"{server_id}.{tool.name}"
                self.tools.append(Tool(
                    name=namespaced_name,
                    description=tool.description,
                    inputSchema=tool.inputSchema
                ))
                self.tool_map[namespaced_name] = (server_id, tool.name)

            self.sessions[server_id] = session
            self.stdio_contexts[server_id] = transport_context

        print(f"Gateway connected to {len(self.sessions)} servers with {len(self.tools)} tools", file=sys.stderr, flush=True)

    async def call_tool(self, name: str, arguments: dict) -> List[TextContent]:
        if name not in self.tool_map:
            return [TextContent(type="text", text=f"Error: Unknown tool '{name}'")]

        server_id, original_name = self.tool_map[name]
        session = self.sessions.get(server_id)
        if not session:
            return [TextContent(type="text", text=f"Error: No session for server '{server_id}'")]

        result = await session.call_tool(original_name, arguments)
        return result.content or [TextContent(type="text", text="")]

    async def close(self):
        for session in self.sessions.values():
            await session.__aexit__(None, None, None)
        for context in self.stdio_contexts.values():
            await context.__aexit__(None, None, None)
        for http_client in self.http_clients.values():
            await http_client.aclose()


app = Server("mcp-gateway")
_gateway: MCPGateway | None = None


@app.list_tools()
async def list_tools() -> list[Tool]:
    if not _gateway:
        return []
    return _gateway.tools


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if not _gateway:
        return [TextContent(type="text", text="Error: gateway not initialized")]
    return await _gateway.call_tool(name, arguments)


async def run_server():
    global _gateway
    print("MCP Gateway starting...", file=sys.stderr, flush=True)

    registry_path = Path(__file__).parent.parent / "mcp_registry.json"
    _gateway = MCPGateway(registry_path=registry_path)
    await _gateway.connect()

    try:
        async with stdio_server() as streams:
            await app.run(streams[0], streams[1], app.create_initialization_options())
    finally:
        if _gateway:
            await _gateway.close()


def main():
    import anyio
    try:
        anyio.run(run_server)
    except KeyboardInterrupt:
        print("Gateway stopped", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
