# MCP Chat App with Mistral on Amazon Bedrock, Strands Agents & MCP Tools

This application provides both command-line and web-based chat interfaces for interacting with AI models from Amazon Bedrock while giving the models access to external tools via the Model Context Protocol (MCP).

## Features

- 🤖 **AI Chat Interface**: Interactive chat with Mistral models on Amazon Bedrock
- 🛠️ **MCP Tools Integration**: Access to Google Maps, time utilities, and knowledge graph tools
- 📷 **Image Upload**: Upload and analyze images with multimodal AI capabilities (Gradio only)
- 🌐 **Web Interface**: Clean, modern Gradio-based web UI
- ⌨️ **Command Line**: Traditional terminal-based chat interface
- 📱 **Real-time Tool Access**: AI can use external tools to answer questions
- ⚙️ **Configuration Management**: Easy configuration via config files

## Available Tools

The application integrates with the following MCP tool servers:

- **Google Maps**: For location-based queries: https://github.com/modelcontextprotocol/servers/tree/main/src/google-maps
- **Time**: For time-related operations:https://github.com/yokingma/time-mcp
- **Memory**: For storing and retrieving information during the conversation: https://github.com/modelcontextprotocol/servers/tree/main/src/memory


## Prerequisites

### Required Environment Variables
```bash
# IMPORTANT: Export AWS region before running
export AWS_REGION=<REGION_NAME>

# Optional: AWS credentials (if not using default profile)
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
```

### Required Dependencies
- Python 3.10+
- Node.js and npm (for MCP servers)
- AWS credentials configured for Bedrock access
- Google Maps API key (for maps functionality)

### Install Python Packages
```bash
pip install -r requirements.txt
```

## Configuration

- Tool servers are configured in the `server_configs.py` file
- AWS Bedrock settings are in the `config.py` file

## Usage

### Web Interface (Gradio)

1. **Set environment variables:**
```bash
export AWS_REGION=<REGION_NAME>>
```

2. **Start the web application:**
```bash
python gradio_app.py
```

3. **Access the interface:**
- **Local**: http://localhost:7860
- **Public URL**: A shareable link will be provided in the console

4. **Features:**
- Type messages in the text box
- Upload images by clicking the image upload area
- Press Enter or click "Send" to submit
- View available tools in the "Available Tools" tab
- Check current configuration in the "Configuration" tab
- Clear chat history with the "Clear Chat" button

### Command Line Interface

1. **Set environment variables:**
```bash
export AWS_REGION=<REGION_NAME>
```

2. **Start the command line chat:**
```bash
python chat.py
```

3. **Usage:**
- Type your messages and press Enter
- Type 'quit', 'exit', or 'q' to exit
- The AI can use tools automatically based on your questions


## Architecture

The application uses the following architecture:

1. **Agent Initialization**: Creates `BedrockModel` and `Agent` from the `strands` library
2. **MCP Client Setup**: Connects to multiple MCP servers using `ExitStack`
3. **Tool Registration**: Loads and registers tools from all MCP clients
4. **Message Processing**: Handles both text and image inputs
5. **Response Generation**: Processes agent responses and extracts text content


## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- Amazon Bedrock for providing access to large language models
- Model Context Protocol (MCP) for the tool integration framework
- Gradio for the web interface components
- Strands Agents: https://github.com/strands-agents