"""
Model Context Protocol (MCP) client implementation module.

Provides a wrapper around the MCP client functionality for connecting to
and communicating with MCP tool servers.
"""
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import json
import time

class MCPClient:
    """
    Model Context Protocol (MCP) client implementation.
    Handles connection and interaction with MCP server for tool management
    and execution.
    """
    def __init__(self, server_params: StdioServerParameters):
        """
        Initialize the MCP client with server parameters.
        
        Args:
            server_params (StdioServerParameters): Configuration for the MCP server
        """
        self.read = None          # Stream reader
        self.write = None         # Stream writer
        self.server_params = server_params  # Server configuration
        self.session = None       # MCP session
        self._client = None       # Internal client instance


    async def __aenter__(self):
        """Async context manager entry point. Establishes connection."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Async context manager exit. Ensures proper cleanup of resources.
        Handles both session and client cleanup.
        """
        await self.cleanup()
        
    async def cleanup(self):
        """
        Clean up resources safely in a way that avoids cancel scope issues.
        
        This bypasses the asyncio scope checking by directly closing resources
        without going through the __aexit__ methods.
        """
        self.session = None
        self._client = None
        self.read = None
        self.write = None

    async def connect(self):
        """
        Establishes connection to MCP server.
        Sets up stdio client, initializes read/write streams,
        and creates client session.
        """
        # Initialize stdio client with server parameters
        self._client = stdio_client(self.server_params)
        
        # Get read/write streams
        self.read, self.write = await self._client.__aenter__()
        
        # Create and initialize session
        session = ClientSession(self.read, self.write)
        self.session = await session.__aenter__()
        await self.session.initialize()

    async def get_available_tools(self):
        """
        List available tools from the MCP server.
        
        Returns:
            list: List of formatted tool specifications compatible with Bedrock
            
        Raises:
            RuntimeError: If not connected to MCP server
        """
        if not self.session:
            raise RuntimeError("Not connected to MCP server")
            
        response = await self.session.list_tools()
        
        # Extract the actual tools from the response
        tools = response.tools if hasattr(response, 'tools') else []
        
        # Convert tools to list of dictionaries with expected attributes
        formatted_tools = [
            {
                'name': tool.name,
                'description': str(tool.description) if tool.description is not None else "No description available",
                'inputSchema': {
                    'json': {
                        'type': 'object',  # Explicitly setting type as 'object' as required by the API
                        'properties': tool.inputSchema.get('properties', {}) if tool.inputSchema else {},
                        'required': tool.inputSchema.get('required', []) if tool.inputSchema else []
                    }
                }
            }
            for tool in tools
        ]
        return formatted_tools

    async def call_tool(self, tool_name, arguments):
        """
        Executes a specific tool with provided arguments.
        
        Args:
            tool_name (str): Name of the tool to execute
            arguments (dict): Tool-specific arguments
            
        Returns:
            dict: Tool execution results with server info
            
        Raises:
            RuntimeError: If not connected to MCP server
        """
        # Verify session exists
        if not self.session:
            raise RuntimeError("Not connected to the MCP Server")

        # Get server info from server_params
        server_info = {
            "command": self.server_params.command,
            "args": self.server_params.args if hasattr(self.server_params, "args") else []
        }
        
        # Get a server name to display
        if server_info["command"] == "npx":
            server_name = server_info["args"][0] if len(server_info["args"]) > 0 else "Unknown NPX Tool"
            if server_name.startswith("-y"):
                server_name = server_info["args"][1] if len(server_info["args"]) > 1 else "Unknown NPX Tool"
        else:
            server_name = server_info["command"]
            
        # Execute tool
        start_time = time.time()
        result = await self.session.call_tool(tool_name, arguments=arguments)
        execution_time = time.time() - start_time
        
        # Augment result with server info
        return {
            "result": result,
            "tool_info": {
                "tool_name": tool_name,
                "server_name": server_name,
                "server_info": server_info,
                "execution_time": f"{execution_time:.2f}s"
            }
        }
