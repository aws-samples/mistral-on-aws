"""
Interactive chat application that connects Amazon Bedrock with MCP tools.

This module provides a chat interface where users can interact with AI models
from Amazon Bedrock while giving the models access to external tools via
the Model Context Protocol (MCP).
"""
import asyncio
from strands import Agent
from strands.tools.mcp import MCPClient
from strands.models import BedrockModel
from mcp import stdio_client, StdioServerParameters
from datetime import datetime
from server_configs import SERVER_CONFIGS
from config import AWS_CONFIG
from contextlib import ExitStack


# ANSI color codes for beautiful output in terminal
class Colors:
    """ANSI color codes for terminal output formatting."""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

def clear_screen():
    """Clear the terminal screen using ANSI escape codes."""
    print('\033[2J\033[H', end='')

def print_welcome():
    """Print a welcome message for the chat application."""
    clear_screen()
    print(f"{Colors.HEADER}{Colors.BOLD}Welcome to AI Assistant!{Colors.END}")
    print(f"{Colors.CYAN}I'm here to help you with any questions or tasks.{Colors.END}")
    print(f"{Colors.CYAN}Type 'quit' to exit.{Colors.END}\n")

def print_tools(tools):
    """
    Print available tools in a formatted list.
    
    Args:
        tools (list): List of MCPAgentTool objects to display
    """
    print(f"{Colors.CYAN}Available Tools:{Colors.END}")
    for tool in tools:
        # Access properties through the tool's methods/attributes
        tool_spec = tool.tool_spec  # This returns the ToolSpec dictionary
        print(f"  • {Colors.GREEN}{tool_spec['name']}{Colors.END}: {tool_spec['description']}")
    print()

def format_message(role: str, content: str) -> str:
    """
    Format a message with appropriate colors and timestamp.
    
    Args:
        role (str): Message role ('user' or 'assistant')
        content (str): Message content
        
    Returns:
        str: Formatted message with colors and timestamp
    """
    timestamp = datetime.now().strftime("%H:%M:%S")
    if role == "user":
        return f"{Colors.BLUE}[{timestamp}] You: {Colors.END}{content}"
    else:
        return f"{Colors.GREEN}Assistant: {Colors.END}{content}"

async def handle_resource_update(uri: str):
    """
    Handle updates to resources from the MCP server.
    
    Args:
        uri (str): URI of the updated resource
    """
    print(f"{Colors.YELLOW}Resource updated: {uri}{Colors.END}")
    
async def main():
    """
    Main function that sets up and runs an interactive AI agent with tool integration.
    
    This function:
    1. Initializes the Bedrock agent with a specified model
    2. Sets up the system prompt for the agent
    3. Connects to MCP servers and registers available tools
    4. Runs an interactive chat loop to handle user input
    5. Ensures proper cleanup of resources
    
    Returns:
        None
    """
    # Initialize model configuration from config.py
    model_id = AWS_CONFIG["model_id"]

    bedrock_model = BedrockModel(
        model_id=model_id,
        streaming=False
    )
    # Define the agent's behavior through system prompt
    system_prompt = """
    You are a helpful assistant that can use tools to help you answer questions and perform tasks.
    Please remember and save user's preferences into memory based on user questions and conversations.
    """
    # Import server configs 
    server_configs = SERVER_CONFIGS
    mcp_clients = [
        MCPClient(lambda cfg=server_config: stdio_client(cfg))
        for server_config in server_configs
    ]
    
    with ExitStack() as stack:
        # Enter all MCP clients and keep them active
        for mcp_client in mcp_clients:
            stack.enter_context(mcp_client)
        
        # Get tools from all clients
        tools = []
        for i, mcp_client in enumerate(mcp_clients):
            try:
                client_tools = mcp_client.list_tools_sync()
                tools.extend(client_tools)
                print(f"Loaded {len(client_tools)} tools from client {i+1}")
            except Exception as e:
                print(f"Error getting tools from MCP client {i+1}: {e}")
        
        try:
            agent = Agent(model=bedrock_model, tools=tools,system_prompt=system_prompt)
        except Exception as e:
            print(f"{Colors.RED}[ERROR] Failed to create agent: {e}{Colors.END}")
            import traceback
            traceback.print_exc()
            return
            
        # Display welcome message and available tools
        print_welcome()
        print_tools(tools)

        # Run interactive chat loop
        try:
            while True:
                user_prompt = input(f"\n{Colors.BOLD}User: {Colors.END}")
                if user_prompt.lower() in ['quit', 'exit', 'q']:
                    print(f"\n{Colors.CYAN}Goodbye! Thanks for chatting!{Colors.END}")
                    
                    # Force immediate termination when user quits
                    import os
                    os._exit(0)
                    
                # if not user_prompt.strip():
                #     continuemy 

                print(f"\n{Colors.YELLOW}Thinking...{Colors.END}")
                try:
                    response = agent(user_prompt)
                except Exception as e:
                    print(f"{Colors.RED}[ERROR] Agent call failed: {e}{Colors.END}")
                    import traceback
                    traceback.print_exc()
                    continue
                
                # Extract the text content from the agent result
                if hasattr(response, 'text'):
                    display_response = response.text
                elif hasattr(response, 'content'):
                    display_response = response.content
                else:
                    # Fallback to string representation
                    display_response = str(response)
                
                print(f"\n{format_message('assistant', display_response)}")
        except KeyboardInterrupt:
            print(f"\n{Colors.CYAN}Goodbye! Thanks for chatting!{Colors.END}")
            
            # Force immediate termination on keyboard interrupt
            import os
            os._exit(0)


if __name__ == "__main__":
    """
    Application entry point.
    
    When run as a script, this initializes and runs the chat application
    using the asyncio event loop.
    """
    try:
        # Patch the asyncio run function to suppress unhandled exceptions during shutdown
        original_run = asyncio.run
        
        def patched_run(main_func, **kwargs):
            try:
                return original_run(main_func, **kwargs)
            finally:
                # Force immediate exit on shutdown to avoid any cleanup errors
                import os
                import signal
                os._exit(0)  # Use os._exit to force immediate termination
        
        # Replace asyncio.run with our patched version
        asyncio.run = patched_run
        
        # Run the application
        asyncio.run(main(), debug=False)
    except KeyboardInterrupt:
        print("\nApplication terminated by user.")
    except Exception as e:
        print(f"Application error: {e}")
    finally:
        # Just in case our patched asyncio.run didn't terminate
        import os
        os._exit(0)