"""MCP Client with AMD LLM integration."""

import os
import json
import asyncio
import getpass
from pathlib import Path
from typing import List, Dict, Any, Tuple
from openai import OpenAI
from mcp import ClientSession
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client


class MCPClient:
    """MCP Client that integrates with AMD LLM Gateway."""
    
    def __init__(self):
        """Initialize the MCP client."""
        self.session: ClientSession | None = None
        self.tools: List[Dict[str, Any]] = []
        self.sessions: Dict[str, ClientSession] = {}
        self.stdio_contexts: Dict[str, Any] = {}
        self.tool_map: Dict[str, Tuple[str, str]] = {}
        self.tool_meta: Dict[str, Dict[str, Any]] = {}
        self.direct_sessions: Dict[str, ClientSession] = {}
        self.direct_contexts: Dict[str, Any] = {}
        self.direct_http_clients: Dict[str, Any] = {}
        self.llm_client = self._setup_llm_client()
        
    def _setup_llm_client(self) -> OpenAI:
        """Setup AMD LLM OpenAI client."""
        api_key = os.environ.get("LLM_GATEWAY_KEY")
        if not api_key:
            raise ValueError("LLM_GATEWAY_KEY environment variable is not set")
        
        try:
            username = getpass.getuser()
        except:
            username = "unknown"
        
        return OpenAI(
            base_url="https://llm-api.amd.com/OpenAI",
            api_key="dummy",
            default_headers={
                "Ocp-Apim-Subscription-Key": api_key,
                "user": username
            }
        )
    
    async def connect_to_server(self, server_script_path: str):
        """Connect to MCP server."""
        import sys
        from mcp.client.stdio import StdioServerParameters
        
        # Get python executable path
        python_path = sys.executable
        
        # Create server parameters
        server_params = StdioServerParameters(
            command=python_path,
            args=[server_script_path],
            env=None
        )
        
        # Create stdio client connection
        self.stdio_context = stdio_client(server_params)
        self.read_stream, self.write_stream = await self.stdio_context.__aenter__()
        
        # Create session
        self.session = ClientSession(self.read_stream, self.write_stream)
        await self.session.__aenter__()
        
        # Initialize session
        await self.session.initialize()
        
        # List available tools
        tools_result = await self.session.list_tools()
        # print("DEBUG: Tool list from MCP gateway: ")
        # print(tools_result)
        # print(tools_result.tools)
        self.tools = self._convert_tools_for_openai(tools_result.tools)
        self.tool_map = {}
        self.tool_meta = {}
        for tool in tools_result.tools:
            tool_name = tool.name
            meta = tool.meta or {}
            server_id = meta.get("server_id", "default")
            # Use original_name hint from gateway meta; fallback to last segment of tool name
            original_name = meta.get("original_name") or tool_name.split(".")[-1]
            self.tool_map[tool_name] = (server_id, original_name)
            self.tool_meta[tool_name] = meta
        
        print(f"Connected to MCP server with {len(self.tools)} tools")

    async def connect_to_registry(self, registry_path: str | None = None):
        """Connect to multiple MCP servers defined in a registry file."""
        import sys
        from mcp.client.stdio import StdioServerParameters

        base_dir = Path(__file__).resolve().parent.parent
        registry_file = Path(registry_path) if registry_path else base_dir / "mcp_registry.json"
        if not registry_file.is_absolute():
            registry_file = base_dir / registry_file

        if not registry_file.exists():
            raise FileNotFoundError(f"Registry file not found: {registry_file}")

        with registry_file.open("r", encoding="utf-8") as f:
            registry = json.load(f)

        servers = registry.get("servers", [])
        if not servers:
            raise ValueError("Registry has no servers configured")

        self.tools = []
        self.tool_map = {}
        self.sessions = {}
        self.stdio_contexts = {}
        self.tool_meta = {}

        for server in servers:
            server_id = server.get("id")
            server_type = server.get("type", "stdio")
            if not server_id:
                raise ValueError("Registry server entry missing 'id'")

            if server_type != "stdio":
                raise ValueError(f"Unsupported server type: {server_type}")

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

            stdio_context = stdio_client(server_params)
            read_stream, write_stream = await stdio_context.__aenter__()

            session = ClientSession(read_stream, write_stream)
            await session.__aenter__()
            await session.initialize()

            tools_result = await session.list_tools()
            namespaced_tools = self._convert_tools_for_openai(
                tools_result.tools,
                namespace=server_id
            )

            for tool in tools_result.tools:
                tool_name = f"{server_id}.{tool.name}"
                original_name = tool.name
                self.tool_map[tool_name] = (server_id, original_name)
                self.tool_meta[tool_name] = tool.meta or {}

            self.tools.extend(namespaced_tools)
            self.sessions[server_id] = session
            self.stdio_contexts[server_id] = stdio_context

        print(f"Connected to {len(self.sessions)} MCP servers with {len(self.tools)} tools")
    
    def _convert_tools_for_openai(self, mcp_tools, namespace: str | None = None) -> List[Dict[str, Any]]:
        """Convert MCP tools to OpenAI function calling format."""
        openai_tools = []
        for tool in mcp_tools:
            tool_name = f"{namespace}.{tool.name}" if namespace else tool.name
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": tool.description,
                    "parameters": tool.inputSchema
                }
            })
        return openai_tools
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Call a tool on the MCP server."""
        # Decide routing: direct (if allowed and supported) or gateway
        if self.sessions:
            if tool_name not in self.tool_map:
                raise RuntimeError(f"Tool not found: {tool_name}")
            server_id, original_name = self.tool_map[tool_name]
            meta = self.tool_meta.get(tool_name, {})

            if meta.get("direct_call_allowed") and meta.get("server_type") in {"sse", "streamable-http"} and meta.get("server_url"):
                print(f"🔧 Direct-calling server tool: {tool_name} -> {server_id}.{original_name}")
                result = await self._call_direct(server_id, original_name, meta, arguments)
            else:
                session = self.sessions.get(server_id)
                if not session:
                    raise RuntimeError(f"Server session not found: {server_id}")
                print(f"🔧 Gateway-calling server tool: {tool_name} -> {server_id}.{original_name}")
                result = await session.call_tool(original_name, arguments)
        else:
            if not self.session:
                raise RuntimeError("Not connected to server")
            meta = self.tool_meta.get(tool_name, {})
            original_name = self.tool_map.get(tool_name, ("default", tool_name))[1]

            if meta.get("direct_call_allowed") and meta.get("server_type") in {"sse", "streamable-http"} and meta.get("server_url"):
                server_id = meta.get("server_id", "default")
                print(f"🔧 Direct-calling server tool: {tool_name} -> {server_id}.{original_name}")
                result = await self._call_direct(server_id, original_name, meta, arguments)
            else:
                print(f"🔧 Gateway-calling server tool: {tool_name}")
                result = await self.session.call_tool(tool_name, arguments)
        print(f"🔧 MCP server returned result")
        
        # Extract text from result
        if result.content:
            return result.content[0].text if result.content else ""
        return ""
    
    async def chat(self, message: str, history: List[Dict[str, str]] = None) -> str:
        """
        Send a chat message and get response.
        
        Args:
            message: User message
            history: Chat history in format [{"role": "user/assistant", "content": "..."}]
            
        Returns:
            Assistant's response
        """
        if not self.session:
            raise RuntimeError("Not connected to server. Call connect_to_server() first.")
        
        # Build messages
        messages = history.copy() if history else []
        messages.append({"role": "user", "content": message})
        
        # First LLM call (run in thread to avoid blocking)
        response = await asyncio.to_thread(
            self.llm_client.chat.completions.create,
            model="gpt-5-mini",
            messages=messages,
            tools=self.tools,
            tool_choice="auto",
            max_tokens=500
        )
        
        response_message = response.choices[0].message
        
        # Check if tools were called
        if response_message.tool_calls:
            # Add assistant's response to messages
            messages.append(response_message)
            
            # Execute tool calls
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                print(f"Calling tool: {function_name} with args: {function_args}")
                
                # Call the tool
                tool_result = await self.call_tool(function_name, function_args)
                
                print(f"✅ Tool result: {tool_result[:100] if len(tool_result) > 100 else tool_result}")
                
                # Add tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": function_name,
                    "content": tool_result
                })
            # print("Tool meta debug:", json.dumps(self.tool_meta, indent=2))

            print(f"🔄 Getting final response from LLM...")
            # Get final response with tool results (run in thread to avoid blocking)
            final_response = await asyncio.to_thread(
                self.llm_client.chat.completions.create,
                model="gpt-5-mini",
                messages=messages,
                max_tokens=500
            )
            
            print(f"✅ Got final response from LLM")
            return final_response.choices[0].message.content
        
        return response_message.content
    
    async def close(self):
        """Close the connection."""
        if self.session:
            await self.session.__aexit__(None, None, None)
        if hasattr(self, 'stdio_context'):
            await self.stdio_context.__aexit__(None, None, None)
        for session in self.sessions.values():
            await session.__aexit__(None, None, None)
        for context in self.stdio_contexts.values():
            await context.__aexit__(None, None, None)
        for session in self.direct_sessions.values():
            try:
                await session.__aexit__(None, None, None)
            except Exception:
                pass
        for context in self.direct_contexts.values():
            try:
                await context.__aexit__(None, None, None)
            except Exception:
                pass
        for http_client in self.direct_http_clients.values():
            try:
                await http_client.aclose()
            except Exception:
                pass

    async def _call_direct(self, server_id: str, original_name: str, meta: Dict[str, Any], arguments: Dict[str, Any]):
        """Directly call a downstream server (HTTP/SSE) when allowed."""
        server_type = meta.get("server_type")
        server_url = meta.get("server_url")
        if not server_url:
            raise RuntimeError("Direct call requested but server_url missing")

        # Reuse or create session
        session = self.direct_sessions.get(server_id)
        if not session:
            if server_type == "streamable-http":
                http_client = create_mcp_http_client()
                self.direct_http_clients[server_id] = http_client
                transport = streamable_http_client(server_url, http_client=http_client)
                read_stream, write_stream, _ = await transport.__aenter__()
            elif server_type == "sse":
                from mcp.client.sse import sse_client
                transport = sse_client(server_url)
                read_stream, write_stream = await transport.__aenter__()
            else:
                raise RuntimeError(f"Direct call not supported for server_type={server_type}")

            session = ClientSession(read_stream, write_stream)
            await session.__aenter__()
            await session.initialize()
            self.direct_sessions[server_id] = session
            self.direct_contexts[server_id] = transport

        return await session.call_tool(original_name, arguments)
