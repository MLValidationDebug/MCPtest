"""Test the MCP client directly."""

import asyncio
import os
from pathlib import Path
from mcp_client.client import MCPClient
from dotenv import load_dotenv

load_dotenv()

async def test_client():
    """Test client in simple async context."""
    print("Creating client...")
    client = MCPClient()
    
    print("Connecting to server...")
    server_path = Path(__file__).parent / "mcp_server" / "server.py"
    await client.connect_to_server(str(server_path))
    
    print(f"Connected! Tools: {len(client.tools)}")
    
    print("\nTesting chat with list_notes...")
    response = await client.chat("List all my notes")
    print(f"Response: {response}")
    
    print("\nTesting chat with calculator...")
    response = await client.chat("What is 5 + 3?")
    print(f"Response: {response}")
    
    print("\nClosing...")
    await client.close()
    print("Done!")

if __name__ == "__main__":
    asyncio.run(test_client())
