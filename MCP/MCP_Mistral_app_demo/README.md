# AI Assistant with Amazon Bedrock & MCP Tools

This project provides a chat interface to interact with AI models from Amazon Bedrock while giving them access to external tools like Google Maps, time utilities, and memory management via the Model Context Protocol (MCP).

## Features

- Chat with large language models through Amazon Bedrock
- Integration with various MCP tool servers (Google Maps, Time, Memory)
- Terminal-based chat interface (chat.py)
- Web-based interface using Gradio (gradio_app.py)

## Requirements

- Python 3.9+
- AWS account with Bedrock access
- Node.js (for MCP tool servers)
- Required Python packages (see requirements.txt)

## Installation

1. Clone this repository:
   ```
   git clone <repository-url>
   cd blog_code
   ```

2. Install required Python packages:
   ```
   pip install -r requirements.txt
   ```

3. Configure AWS credentials:
   ```
   aws configure
   ```

## Running the Application

### Terminal-based Interface

Run the terminal-based interface with:

```bash
python src/chat.py
```

### Gradio Web Interface

Run the web-based interface with:

```bash
# Make sure you're in the root directory of the project
cd /path/to/blog_code
python gradio_app.py
```

This will start a local web server and provide you with a URL (typically http://127.0.0.1:7860) to access the application in your browser. The application must be run from the project's root directory so that it can correctly import modules from the src directory.

## Usage

1. Start the application using one of the methods above
2. Type your queries and questions in the input field
3. The AI assistant will respond and use available tools as needed
4. Type 'quit', 'exit', or 'q' to exit the application

## Available Tools

The application integrates with the following MCP tool servers:

- **Google Maps**: For location-based queries
- **Time**: For time-related operations
- **Memory**: For storing and retrieving information during the conversation

## Configuration

Tool servers are configured in the `server_configs.py` file. You can modify this file to add, remove, or reconfigure tool servers.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- Amazon Bedrock for providing access to large language models
- ModelContextProtocol (MCP) for the tool integration framework