"""Test script to verify MCP server works."""

import asyncio
import sys
from pathlib import Path
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

async def test_server():
    """Test the MCP server."""
    print("Testing MCP Server...")
    
    # Get paths
    python_path = sys.executable
    server_path = Path(__file__).parent / "mcp_server" / "server.py"
    
    print(f"Python: {python_path}")
    print(f"Server: {server_path}")
    
    # Create server parameters
    server_params = StdioServerParameters(
        command=python_path,
        args=[str(server_path)]
    )
    
    try:
        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                # Initialize
                await session.initialize()
                print("✅ Server initialized!")
                
                # List tools
                tools = await session.list_tools()
                print(f"✅ Found {len(tools.tools)} tools:")
                for tool in tools.tools:
                    print(f"   - {tool.name}: {tool.description}")
                
                # Test calculator
                print("\nTesting calculator...")
                result = await session.call_tool("calculator", {
                    "operation": "add",
                    "a": 5,
                    "b": 3
                })
                print(f"✅ Calculator result: {result.content[0].text}")
                
                # Test create note
                print("\nTesting create_note...")
                result = await session.call_tool("create_note", {
                    "title": "Test Note",
                    "content": "This is a test"
                })
                print(f"✅ Note created: {result.content[0].text}")
                
                # Test list notes
                print("\nTesting list_notes...")
                result = await session.call_tool("list_notes", {})
                print(f"✅ Notes: {result.content[0].text}")
                
                print("\n🎉 All tests passed!")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_server())
