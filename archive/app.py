"""Main application launcher for MCP Chat Demo."""

import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv
import threading

# Load environment variables
load_dotenv()

from mcp_client.client import MCPClient
from mcp_client.ui import ChatUI


# Global client instance
client = None


async def setup_client():
    """Setup MCP client."""
    global client
    
    # Check for API key
    if not os.environ.get("LLM_GATEWAY_KEY"):
        print("❌ Error: LLM_GATEWAY_KEY environment variable is not set!")
        print("Please set it in your .env file or environment.")
        return False
    
    print("🚀 Starting MCP Chat Demo...")
    print("📡 Connecting to MCP server...")
    
    # Create MCP client
    client = MCPClient()
    
    try:
        # Connect to gateway server
        gateway_path = Path(__file__).parent / "mcp_gateway" / "server.py"
        await client.connect_to_server(str(gateway_path))
        print(f"✅ Connected! Available tools: {len(client.tools)}")
        return True
        
    except Exception as e:
        print(f"❌ Error connecting to server: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Entry point."""
    # Run everything in the same event loop
    asyncio.run(async_main())


async def async_main():
    """Async main function."""
    global client
    
    success = await setup_client()
    
    if not success:
        print("Failed to start server")
        return
    
    try:
        # Create and launch UI
        print("🎨 Launching chat UI...")
        print("🌐 Open http://localhost:7862 in your browser")
        ui = ChatUI(client)
        
        ui.launch(
            server_name="0.0.0.0",
            server_port=7862,
            share=False,
            inbrowser=True
        )
        
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        if client:
            print("👋 Shutting down...")
            loop.run_until_complete(client.close())


if __name__ == "__main__":
    main()
