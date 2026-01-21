"""MCP Gateway Server that aggregates tools from registered MCP servers.

Adds basic dynamic registration:
- Admin tools (optional token) to register / unregister / list servers
- In-memory reload without restarting the gateway
- Registry persisted back to the JSON file used at startup
"""

import json
import os
import sys
import asyncio
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
        self.registry_entries: Dict[str, dict] = {}
        self.sessions: Dict[str, ClientSession] = {}
        self.stdio_contexts: Dict[str, any] = {}
        self.http_clients: Dict[str, any] = {}
        self.server_tools: Dict[str, List[Tool]] = {}
        self.tools: List[Tool] = []
        self.tool_map: Dict[str, Tuple[str, str]] = {}

    # --- Registry helpers -------------------------------------------------

    def _load_registry(self) -> dict:
        if not self.registry_path.exists():
            raise FileNotFoundError(f"Registry file not found: {self.registry_path}")
        with self.registry_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _persist_registry(self) -> None:
        """Persist current registry_entries back to the registry file."""
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"servers": list(self.registry_entries.values())}
        with self.registry_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    async def _with_timeout(self, coro, timeout: float, context: str):
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError as exc:
            raise TimeoutError(f"Timeout while {context}") from exc

    async def _await_with_timeout(self, awaitable, timeout_s: float, context: str):
        """Await with timeout to avoid hanging on bad endpoints."""
        try:
            return await asyncio.wait_for(awaitable, timeout=timeout_s)
        except asyncio.TimeoutError as exc:
            raise TimeoutError(f"Timeout while {context}") from exc

    async def _connect_entry(self, server: dict) -> None:
        """Connect to a single server entry and register its tools."""
        server_id = server.get("id")
        server_type = server.get("type", "stdio")
        if not server_id:
            raise ValueError("Registry server entry missing 'id'")
        headers = server.get("headers")
        base_dir = self.registry_path.parent

        if server_type == "stdio":
            command = server.get("command") or sys.executable
            if not command:
                raise ValueError("'command' is required for stdio servers")
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
            read_stream, write_stream = await self._await_with_timeout(
                transport_context.__aenter__(), 10,
                f"connecting to stdio server '{server_id}'"
            )

        elif server_type == "sse":
            url = server.get("url")
            if not url or not str(url).startswith("http"):
                raise ValueError(f"Server '{server_id}' missing valid 'url' for SSE")
            transport_context = sse_client(url, headers=headers)
            read_stream, write_stream = await self._await_with_timeout(
                transport_context.__aenter__(), 10,
                f"connecting to SSE server '{server_id}'"
            )

        elif server_type == "streamable-http":
            url = server.get("url")
            if not url or not str(url).startswith("http"):
                raise ValueError(f"Server '{server_id}' missing valid 'url' for streamable-http")
            http_client = create_mcp_http_client(headers=headers)
            self.http_clients[server_id] = http_client
            transport_context = streamable_http_client(url, http_client=http_client)
            read_stream, write_stream, _ = await self._await_with_timeout(
                transport_context.__aenter__(), 10,
                f"connecting to streamable-http server '{server_id}'"
            )

        else:
            raise ValueError(f"Unsupported server type: {server_type}")

        session = ClientSession(read_stream, write_stream)
        await session.__aenter__()
        await self._with_timeout(session.initialize(), 10, f"initializing server '{server_id}'")

        tools_result = await self._with_timeout(session.list_tools(), 10, f"listing tools for '{server_id}'")
        namespaced = []
        for tool in tools_result.tools:
            namespaced_name = f"{server_id}.{tool.name}"

            # Attach routing metadata so clients can optionally bypass the gateway for HTTP/SSE servers.
            meta: dict = {
                "server_id": server_id,
                "server_type": server_type,
                "original_name": tool.name,
            }
            if server_type in {"sse", "streamable-http"}:
                meta["server_url"] = server.get("url")
                meta["direct_call_allowed"] = True
            else:
                meta["direct_call_allowed"] = False

            # Use alias name `_meta` to ensure metadata survives serialization
            namespaced.append(Tool(
                name=namespaced_name,
                description=tool.description,
                inputSchema=tool.inputSchema,
                _meta=meta
            ))
            # Optional debug: confirm meta attached during connection
            if os.environ.get("MCP_GATEWAY_DEBUG"):
                print(f"[gateway] attached meta for {namespaced_name}: {meta}", file=sys.stderr, flush=True)
            self.tool_map[namespaced_name] = (server_id, tool.name)

        self.sessions[server_id] = session
        self.stdio_contexts[server_id] = transport_context
        self.server_tools[server_id] = namespaced
        # print(f"[gateway] connected server '{server_id}' with {len(namespaced)} tools", file=sys.stderr, flush=True)

    async def _disconnect_entry(self, server_id: str) -> None:
        """Disconnect a server and remove its tools."""
        if server_id in self.sessions:
            try:
                await self.sessions[server_id].__aexit__(None, None, None)
            except Exception:
                pass
            del self.sessions[server_id]
        if server_id in self.stdio_contexts:
            try:
                await self.stdio_contexts[server_id].__aexit__(None, None, None)
            except Exception:
                pass
            del self.stdio_contexts[server_id]
        if server_id in self.http_clients:
            try:
                await self.http_clients[server_id].aclose()
            except Exception:
                pass
            del self.http_clients[server_id]
        if server_id in self.server_tools:
            del self.server_tools[server_id]

        # Remove tool mappings belonging to this server
        to_remove = [name for name, pair in self.tool_map.items() if pair[0] == server_id]
        for name in to_remove:
            del self.tool_map[name]

    def _rebuild_tool_list(self) -> None:
        """Rebuild aggregated tool list from per-server lists."""
        aggregated: List[Tool] = []
        for tools in self.server_tools.values():
            aggregated.extend(tools)
        self.tools = aggregated

    async def connect(self):
        registry = self._load_registry()
        servers = registry.get("servers", [])
        if not servers:
            raise ValueError("Registry has no servers configured")

        self.registry_entries = {srv["id"]: srv for srv in servers}
        self.tools = []
        self.tool_map = {}
        self.sessions = {}
        self.stdio_contexts = {}
        self.http_clients = {}
        self.server_tools = {}

        for server in servers:
            await self._connect_entry(server)

        self._rebuild_tool_list()
        print(f"Gateway connected to {len(self.sessions)} servers with {len(self.tools)} tools", file=sys.stderr, flush=True)

    async def register_server(self, server: dict) -> dict:
        """Register (or update) a server at runtime and connect to it."""
        server_id = server.get("id")
        if not server_id:
            return {"status": "error", "message": "Missing required field 'id'"}

        # Disconnect if exists
        if server_id in self.registry_entries:
            await self._disconnect_entry(server_id)

        self.registry_entries[server_id] = server
        try:
            print(f"[gateway] registering server '{server_id}'", file=sys.stderr, flush=True)
            await self._with_timeout(self._connect_entry(server), 20, f"connecting server '{server_id}'")
            self._rebuild_tool_list()
            self._persist_registry()
            print(f"[gateway] registered server '{server_id}'", file=sys.stderr, flush=True)
            return {"status": "ok", "message": f"Registered {server_id}"}
        except Exception as e:
            # Roll back registry entry on failure
            print(f"[gateway] failed to register '{server_id}': {e}", file=sys.stderr, flush=True)
            if server_id in self.registry_entries:
                del self.registry_entries[server_id]
            await self._disconnect_entry(server_id)
            return {"status": "error", "message": str(e)}

    async def unregister_server(self, server_id: str) -> dict:
        """Unregister a server and disconnect."""
        if server_id not in self.registry_entries:
            return {"status": "error", "message": f"Server '{server_id}' not found"}

        del self.registry_entries[server_id]
        await self._disconnect_entry(server_id)
        self._rebuild_tool_list()
        self._persist_registry()
        return {"status": "ok", "message": f"Unregistered {server_id}"}

    def list_registry(self) -> dict:
        """Return current registry entries."""
        return {"servers": list(self.registry_entries.values())}

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
        for session in list(self.sessions.values()):
            try:
                await session.__aexit__(None, None, None)
            except Exception:
                pass
        for context in list(self.stdio_contexts.values()):
            try:
                await context.__aexit__(None, None, None)
            except Exception:
                pass
        for http_client in list(self.http_clients.values()):
            try:
                await http_client.aclose()
            except Exception:
                pass


app = Server("mcp-gateway")
_gateway: MCPGateway | None = None


ADMIN_TOOLS: list[Tool] = [
    Tool(
        name="admin.list_servers",
        description="List registered servers on the gateway",
        inputSchema={"type": "object", "properties": {"admin_token": {"type": "string"}}},
    ),
    Tool(
        name="admin.register_server",
        description="Register or update a downstream MCP server",
        inputSchema={
            "type": "object",
            "properties": {
                "admin_token": {"type": "string"},
                "id": {"type": "string", "description": "Unique server id"},
                "type": {"type": "string", "enum": ["stdio", "sse", "streamable-http"], "default": "stdio"},
                "command": {"type": "string", "description": "Command for stdio servers"},
                "args": {"type": "array", "items": {"type": "string"}, "description": "Args for stdio command"},
                "env": {"type": "object", "additionalProperties": {"type": "string"}},
                "url": {"type": "string", "description": "URL for sse/streamable-http"},
                "headers": {"type": "object", "additionalProperties": {"type": "string"}},
            },
            "required": ["id"],
        },
    ),
    Tool(
        name="admin.unregister_server",
        description="Unregister a downstream MCP server",
        inputSchema={
            "type": "object",
            "properties": {
                "admin_token": {"type": "string"},
                "id": {"type": "string", "description": "Server id to remove"},
            },
            "required": ["id"],
        },
    ),
]


def _is_admin_ok(arguments: dict) -> bool:
    token = os.environ.get("MCP_GATEWAY_ADMIN_TOKEN")
    if not token:
        return True
    return arguments.get("admin_token") == token


@app.list_tools()
async def list_tools() -> list[Tool]:
    if not _gateway:
        return []
    # Optional debug: show sample meta to confirm direct-call hints propagate
    if os.environ.get("MCP_GATEWAY_DEBUG"):
        try:
            sample = next((t for t in _gateway.tools if t.name.startswith("http-remote")), None)
            if sample:
                print("[gateway] sample tool meta", sample.name, sample.meta, file=sys.stderr, flush=True)
        except Exception:
            pass
    return _gateway.tools + ADMIN_TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if not _gateway:
        return [TextContent(type="text", text="Error: gateway not initialized")]

    try:
        # Strip null admin_token to avoid schema validation issues
        if isinstance(arguments, dict) and arguments.get("admin_token") is None:
            arguments = {k: v for k, v in arguments.items() if k != "admin_token"}

        # Admin surface
        if name.startswith("admin."):
            if not _is_admin_ok(arguments or {}):
                return [TextContent(type="text", text="Error: unauthorized")]

            if name == "admin.list_servers":
                return [TextContent(type="text", text=json.dumps(_gateway.list_registry(), indent=2))]

            if name == "admin.register_server":
                result = await _gateway.register_server(arguments)
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            if name == "admin.unregister_server":
                result = await _gateway.unregister_server(arguments.get("id", ""))
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            return [TextContent(type="text", text="Error: unknown admin tool")]

        return await _gateway.call_tool(name, arguments)
    except Exception as e:
        # Keep the gateway alive and return the error
        return [TextContent(type="text", text=f"Error: {e}")]


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
        # Swallow known cancel-scope shutdown issues to keep process alive in demo scenarios
        msg = str(e)
        if "cancel scope" in msg:
            print(f"Gateway shutdown warning: {e}", file=sys.stderr, flush=True)
            sys.exit(0)
        print(f"Fatal error: {e}", file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
