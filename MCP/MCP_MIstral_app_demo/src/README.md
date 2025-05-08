# MCP Tools CLI Chat Application

This directory contains the core components for interacting with the Model Context Protocol (MCP) tools through a command-line interface using Amazon Bedrock models.

## Getting Started with the CLI Chat App

The `chat.py` module provides a terminal-based interface for conversing with AI models from Amazon Bedrock with access to external tools via MCP.

### Prerequisites

Before running the CLI chat application, ensure you have:

1. Python 3.8 or higher installed
2. AWS credentials configured (either via environment variables, AWS CLI configuration, or IAM role)
3. All required Python packages installed from the requirements.txt file in the parent directory

### Installation

1. Clone the repository or download the code
2. Navigate to the parent directory of this project
3. Install the required dependencies:

```bash
pip install -r requirements.txt
```

### Using chat.py

To start the chat application, navigate to the parent directory and run:

```bash
cd src
python chat.py
```

This will launch the interactive CLI chat interface with the following features:

- Terminal-based chat interface
- Automatic connection to configured MCP servers
- Display of available tools and their descriptions
- Real-time interaction with the AI assistant

### Chat Commands

While in the chat session, you can use these commands:

- Type your message and press Enter to send it to the AI assistant
- Type `quit`, `exit`, or `q` to exit the application
- Press Ctrl+C to force quit the application

### Configuration

The chat application uses:

- MCP server configurations from `server_configs.py`
- Custom prompt configurations in the `agent.py` module
