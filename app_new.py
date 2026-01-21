"""Main application launcher for MCP Chat Demo - Refactored for proper async handling."""

import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from threading import Thread
from concurrent.futures import ThreadPoolExecutor
import queue

# Load environment variables
load_dotenv()

from mcp_client.client import MCPClient
from mcp_client.ui_new import ChatUI


class MCPClientManager:
    """Manages MCP client in a dedicated thread with its own event loop."""
    
    def __init__(self):
        self.client = None
        self.loop = None
        self.thread = None
        self.ready = False
        
    def start(self):
        """Start the client manager thread."""
        print("🚀 Starting MCP Chat Demo...")
        
        # Check for API key
        if not os.environ.get("LLM_GATEWAY_KEY"):
            print("❌ Error: LLM_GATEWAY_KEY environment variable is not set!")
            print("Please set it in your .env file or environment.")
            return False
        
        # Create new event loop for this thread
        self.loop = asyncio.new_event_loop()
        
        # Start thread
        self.thread = Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        
        # Wait for setup
        print("📡 Connecting to MCP server...")
        future = asyncio.run_coroutine_threadsafe(self._setup(), self.loop)
        # Allow more time for gateway startup / remote servers
        success = future.result(timeout=30)
        
        if success:
            self.ready = True
            print(f"✅ Connected! Available tools: {len(self.client.tools)}")
        
        return success
    
    def _run_loop(self):
        """Run the event loop in this thread."""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
    
    async def _setup(self):
        """Setup the MCP client (runs in dedicated thread)."""
        try:
            self.client = MCPClient()
            gateway_path = Path(__file__).parent / "mcp_gateway" / "server.py"
            await self.client.connect_to_server(str(gateway_path))
            return True
        except Exception as e:
            print(f"❌ Error connecting to server: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def chat(self, message: str, history=None):
        """
        Send a chat message (synchronous wrapper).
        
        Args:
            message: User message
            history: Chat history
            
        Returns:
            Assistant response
        """
        if not self.ready:
            return "Error: Client not ready"
        
        # Run the async chat method in the client's event loop
        future = asyncio.run_coroutine_threadsafe(
            self.client.chat(message, history),
            self.loop
        )
        
        try:
            return future.result(timeout=60)
        except Exception as e:
            print(f"❌ Chat error: {e}")
            import traceback
            traceback.print_exc()
            return f"Error: {str(e)}"
    
    def stop(self):
        """Stop the client manager."""
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)


def main():
    """Entry point."""
    # Create and start client manager
    manager = MCPClientManager()
    
    if not manager.start():
        print("Failed to start server")
        return
    
    try:
        # Create and launch UI
        print("🎨 Launching chat UI...")
        print("🌐 Open http://localhost:7862 in your browser")
        
        ui = ChatUI(manager)
        
        ui.launch(
            server_name="0.0.0.0",
            server_port=7862,
            share=False,
            inbrowser=True
        )
    
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
    finally:
        manager.stop()


if __name__ == "__main__":
    main()
