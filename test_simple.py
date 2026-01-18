"""Test simple server."""

import asyncio
import sys
from pathlib import Path
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

async def test():
    python_path = sys.executable
    server_path = Path(__file__).parent / "simple_server.py"
    
    server_params = StdioServerParameters(
        command=python_path,
        args=[str(server_path)]
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("✅ Connected!")
            
            tools = await session.list_tools()
            print(f"✅ Tools: {[t.name for t in tools.tools]}")
            
            result = await session.call_tool("add", {"a": 5, "b": 3})
            print(f"✅ Result: {result.content[0].text}")

if __name__ == "__main__":
    asyncio.run(test())
