"""Gradio chat UI for MCP demo."""

import gradio as gr
from typing import List, Tuple
import asyncio
from concurrent.futures import ThreadPoolExecutor


class ChatUI:
    """Chat interface using Gradio."""
    
    def __init__(self, mcp_client):
        """
        Initialize chat UI.
        
        Args:
            mcp_client: MCPClient instance
        """
        self.mcp_client = mcp_client
        self.chat_history = []
    
    async def respond(self, message: str, history: List[dict]):
        """
        Process user message and generate response.
        
        Args:
            message: User message
            history: Chat history as list of message dicts with 'role' and 'content'
            
        Yields:
            Updated history after each step
        """
        print(f"\n📥 Received message: {message}")
        print(f"📜 History length: {len(history)}")
        
        # First, add user message and yield to show it immediately
        history.append({"role": "user", "content": message})
        yield history
        
        # Convert Gradio history format to OpenAI format (filter out system messages if any)
        openai_history = [msg for msg in history if msg.get("role") in ["user", "assistant"]]
        print(f"📤 Sending to LLM with {len(openai_history)} history messages")
        
        # Get response from MCP client
        try:
            response = await self.mcp_client.chat(message, openai_history[:-1])  # Exclude the user message we just added
            print(f"✅ Got response: {response[:100]}...")
        except Exception as e:
            response = f"Error: {str(e)}"
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
        
        # Add assistant response and yield
        history.append({"role": "assistant", "content": response})
        
        print(f"📦 Returning updated history with {len(history)} messages\n")
        yield history
    
    async def respond_and_clear(self, message: str, history: List[dict]):
        """Wrapper that clears the textbox while processing."""
        async for updated_history in self.respond(message, history):
            yield "", updated_history
    
    def create_interface(self) -> gr.Blocks:
        """Create Gradio interface."""
        
        with gr.Blocks(title="MCP Chat Demo") as interface:
            gr.Markdown(
                """
                # 🤖 MCP Chat Demo
                
                Chat with an AI assistant that has access to MCP tools:
                - **Calculator**: Perform arithmetic operations
                - **Notes**: Create and manage notes
                - **Time**: Get current time in different timezones
                - **System Info**: Get basic system and runtime info (external server)
                
                Try asking:
                - "What's 15 multiplied by 23?"
                - "Create a note titled 'Todo' with content 'Buy groceries'"
                - "What time is it in Tokyo?"
                - "Get system info"
                - "List all my notes"
                """
            )
            
            chatbot = gr.Chatbot(
                label="Chat",
                height=500,
                show_label=False
            )
            
            with gr.Row():
                msg = gr.Textbox(
                    label="Message",
                    placeholder="Type your message here...",
                    show_label=False,
                    scale=4
                )
                send_btn = gr.Button("Send", variant="primary", scale=1)
            
            gr.Examples(
                examples=[
                    "Calculate 25 * 4 + 10",
                    "Create a note titled 'Meeting' with content 'Team sync at 3pm tomorrow'",
                    "What time is it in New York?",
                    "Get system info",
                    "List all my notes",
                    "What's 100 divided by 5?",
                ],
                inputs=msg
            )
            
            # Event handlers - Gradio 4.x supports async generators
            msg.submit(self.respond_and_clear, [msg, chatbot], [msg, chatbot])
            send_btn.click(self.respond_and_clear, [msg, chatbot], [msg, chatbot])
        
        return interface
    
    def launch(self, **kwargs):
        """Launch the Gradio interface."""
        interface = self.create_interface()
        interface.launch(**kwargs)
