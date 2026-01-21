# MCP Chat Demo

A complete Model Context Protocol (MCP) demonstration with:
- **MCP Server** with useful tools (calculator, notes, time utilities)
- **MCP Client** integrated with AMD LLM Gateway API
- **Interactive Chat UI** built with Gradio

All components use the official MCP Python SDK.

## Features

### MCP Server Tools
- **Calculator**: Perform arithmetic operations
- **Notes**: Create, read, list, and delete notes
- **Time**: Get current time in different timezones

### Chat Interface
- Web-based chat UI powered by Gradio
- AMD LLM integration (gpt-5-mini model)
- Tool calling through MCP protocol
- Real-time interaction with MCP server

## Prerequisites

- Python 3.10 or higher
- AMD LLM Gateway API key

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up your API key:
```bash
# Windows PowerShell
$env:LLM_GATEWAY_KEY="<your_llm_gateway_key>"

# Or create .env file
echo LLM_GATEWAY_KEY=<your_llm_gateway_key> > .env
```

## Quick Start

Run the complete demo:
```bash
python app.py
```

This will:
1. Start the MCP server in the background
2. Launch the chat UI at `http://localhost:7860`
3. Connect everything together

## Project Structure

```
MCPtest/
├── mcp_server/
│   ├── __init__.py
│   ├── server.py          # MCP server implementation
│   └── tools/             # Server-side tools
│       ├── calculator.py
│       ├── notes.py
│       └── time_utils.py
├── mcp_client/
│   ├── __init__.py
│   ├── client.py          # MCP client with AMD LLM
│   └── ui.py              # Gradio chat interface
├── app.py                 # Main application launcher
├── requirements.txt
└── README.md
```

## Usage

1. Open your browser to `http://localhost:7860`
2. Type your message in the chat interface
3. The AI assistant can use MCP tools to help you:
   - "Calculate 15 * 23"
   - "Create a note titled 'Meeting' with content 'Team sync at 3pm'"
   - "What time is it in Tokyo?"
   - "List all my notes"

## How It Works

1. **User Input** → Gradio UI captures your message
2. **MCP Client** → Sends message to AMD LLM with available tools
3. **AMD LLM** → Decides if tools are needed and calls them
4. **MCP Server** → Executes tool requests and returns results
5. **Response** → AI generates final response using tool results
6. **UI Update** → Chat displays the response

## Technical Details

- **MCP SDK**: Official Python `mcp` package
- **LLM**: AMD LLM Gateway (gpt-5-mini)
- **UI Framework**: Gradio 4.x
- **Communication**: stdio transport between client and server

## License

MIT
