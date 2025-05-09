"""
Utility module for managing external tools integration with Amazon Bedrock.
Provides functionality for tool registration, execution, and compatibility with Bedrock's requirements.
"""
import json


class UtilityHelper:
    """
    Manages the integration of external tools with Amazon Bedrock.
    
    This class handles:
    - Tool registration and name normalization
    - Tool specification generation for Bedrock API
    - Tool execution and error handling
    """
    def __init__(self):
        """Initialize the tool registry."""
        self._tools = {}
        self._name_mapping = {}

    @staticmethod
    def _correct_name(name):
        """
        Convert tool names to Bedrock-compatible format.
        
        Args:
            name (str): Original tool name
            
        Returns:
            str: Normalized tool name with hyphens replaced by underscores
        """
        return name.replace("-", "_")

    def register_tool(self, name, func, description, input_schema):
        """
        Register a new tool with the system.
        
        Args:
            name (str): Original name of the tool
            func (callable): Async function that implements the tool
            description (str): Tool description for AI model
            input_schema (dict): JSON schema describing tool's input parameters
        """
        corrected_name = UtilityHelper._correct_name(name)
        self._name_mapping[corrected_name] = name
        self._tools[corrected_name] = {
            "function": func,
            "description": description,
            "input_schema": input_schema,
            "original_name": name,
        }

    def get_tools(self):
        """
        Generate tool specifications for Bedrock API.
        
        Returns:
            dict: Tool configurations in the format expected by Bedrock
        """
        tool_specs = []
        for corrected_name, tool in self._tools.items():
            # Ensure the inputSchema.json.type is explicitly set to 'object' as required by the API
            input_schema = tool["input_schema"].copy()
            if 'json' in input_schema and 'type' not in input_schema['json']:
                input_schema['json']['type'] = 'object'
                
            tool_specs.append(
                {
                    "toolSpec": {
                        "name": corrected_name,
                        "description": tool["description"],
                        "inputSchema": input_schema,
                    }
                }
            )

        return {"tools": tool_specs}

    async def execute_tool(self, payload):
        """
        Execute a tool based on the model's request.
        
        Args:
            payload (dict): Tool execution request with toolUseId, name, and input
            
        Returns:
            dict: Tool execution result with status and content
            
        Raises:
            ValueError: If the requested tool is not found
        """
        tool_use_id = payload["toolUseId"]
        corrected_name = payload["name"]
        tool_input = payload["input"]

        if corrected_name not in self._tools:
            raise ValueError(f"Unknown tool {corrected_name} not found")

        try:
            tool_func = self._tools[corrected_name]["function"]
            original_name = self._tools[corrected_name]["original_name"]
            
            # Track tool usage for UI display if callback is set
            if hasattr(self, 'tool_usage_callback') and self.tool_usage_callback:
                # Notify about tool invocation
                self.tool_usage_callback({
                    "event": "tool_start",
                    "tool_name": original_name,
                    "input": tool_input
                })
            
            # Execute the tool
            result_data = await tool_func(original_name, tool_input)
            
            # Extract the actual result and tool info
            if isinstance(result_data, dict) and "result" in result_data and "tool_info" in result_data:
                result = result_data["result"]
                tool_info = result_data["tool_info"]
                
                # Notify about tool completion if callback exists
                if hasattr(self, 'tool_usage_callback') and self.tool_usage_callback:
                    self.tool_usage_callback({
                        "event": "tool_complete",
                        "tool_name": original_name,
                        "tool_info": tool_info,
                        "status": "success"
                    })
            else:
                # Handle legacy format
                result = result_data
                tool_info = {"tool_name": original_name}
            
            return {
                "toolUseId": tool_use_id,
                "content": [{"text": str(result)}],
                "status": "success",
            }

        except Exception as e:
            # Notify about tool error if callback exists
            if hasattr(self, 'tool_usage_callback') and self.tool_usage_callback:
                self.tool_usage_callback({
                    "event": "tool_error",
                    "tool_name": original_name,
                    "error": str(e)
                })
                
            return {
                "toolUseId": tool_use_id,
                "content": [{"text": f"Error executing tool: {str(e)}"}],
                "status": "error",
            }
            
    def register_tool_usage_callback(self, callback):
        """
        Register a callback function to be called whenever a tool is used.
        
        Args:
            callback (callable): Function to call with tool usage information
        """
        self.tool_usage_callback = callback

    def clear_tools(self):
        """Remove all registered tools."""
        self._tools.clear()
        self._name_mapping.clear()
