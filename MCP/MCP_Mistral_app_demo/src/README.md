# MCP Tools Chat Application Source Code

This directory contains the core components for interacting with the Model Context Protocol (MCP) tools through both command-line and web interfaces using Amazon Bedrock models.

## Core Components

- **agent.py**: Handles interactions with Amazon Bedrock models, manages conversation context, and processes multimodal inputs (text and images)
- **chat.py**: Provides a terminal-based interface for conversing with AI models
- **config.py**: Contains configuration parameters for AWS Bedrock services
- **mcpclient.py**: Client implementation for connecting to MCP servers
- **server_configs.py**: Defines the available MCP server configurations
- **utility.py**: Utility functions for tool management and execution

## Getting Started with the CLI Chat App

The `chat.py` module provides a terminal-based interface for conversing with AI models from Amazon Bedrock with access to external tools via MCP.

### Prerequisites

Before running the CLI chat application, ensure you have:

1. Python 3.9 or higher installed
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
- Support for image URLs in messages

### Chat Commands

While in the chat session, you can use these commands:

- Type your message and press Enter to send it to the AI assistant
- Include image URLs in your message for visual understanding
- Type `quit`, `exit`, or `q` to exit the application
- Press Ctrl+C to force quit the application

## Multimodal Support

The application supports multimodal interactions through:

- Automatic detection of image URLs in user messages
- Processing and optimization of images for compatibility with Bedrock models
- Support for various image formats (JPEG, PNG, GIF, WebP)
- Dynamic content handling in the conversation flow

## Configuration

The application configuration is managed through:

- **server_configs.py**: MCP server connections and parameters
- **config.py**: AWS Bedrock settings (region and model ID)
- **agent.py**: System prompts and model behavior settings

## Working with Images

The `agent.py` module includes functionality to:
- Detect image URLs in user input
- Fetch and process images from URLs
- Resize large images for API compatibility
- Convert between image formats as needed
- Package images correctly for the Bedrock Converse API

## Sample Questions

- Q: Based on this image: https://images.pexels.com/photos/70497/pexels-photo-70497.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=1, can you suggest some restaurants in London?

- Q: https://images.pexels.com/photos/70497/pexels-photo-70497.jpeg What ingredients do you see in this dish?
