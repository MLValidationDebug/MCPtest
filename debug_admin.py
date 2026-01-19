import asyncio, sys
from pathlib import Path
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp import ClientSession

gp = Path("mcp_gateway/server.py").resolve()

async def main():
    params = StdioServerParameters(command=sys.executable, args=[str(gp)])
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            res = await asyncio.wait_for(
                s.call_tool(
                    "admin.register_server",
                    {
                        "admin_token": "test",
                        "id": "test-ext-b",
                        "type": "stdio",
                        "command": "python",
                        "args": ["mcp_server_external/server.py"],
                    },
                ),
                15,
            )
            print("register:", res.content[0].text)
            res2 = await s.call_tool("admin.list_servers", {})
            print("list:", res2.content[0].text)

asyncio.run(main())
