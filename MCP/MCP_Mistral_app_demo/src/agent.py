"""
Agent module for interacting with Amazon Bedrock models and handling tools execution.
"""
import boto3
import asyncio
import re
from botocore.config import Config
from botocore.exceptions import ClientError


class BedrockConverseAgent:
    """
    Agent class for interacting with Amazon Bedrock models.
    
    Handles communication with the model, manages conversation context,
    and processes tool invocations from the model's responses.
    """
    def __init__(self, model_id, region='us-west-2', system_prompt='You are a helpful assistant.'):
        """
        Initialize the Bedrock agent with model configuration.
        
        Args:
            model_id (str): The Bedrock model ID to use
            region (str): AWS region for Bedrock service
            system_prompt (str): System instructions for the model
        """
        self.model_id = model_id
        self.region = region

        # # Configure retry strategy
        # retry_config = Config(
        #     region_name=self.region,
        #     retries=dict(
        #         max_attempts=5,  # Number of retry attempts
        #         mode="adaptive",  # Adaptive or standard mode
        #         total_max_attempts=10,  # Including initial call
        #     ),
        #     connect_timeout=5,  # Connection timeout in seconds
        #     read_timeout=60,  # Read timeout in seconds
        #     max_pool_connections=10,  # Max concurrent connections
        # )

        # self.client = boto3.client('bedrock-runtime', region_name=self.region, config=retry_config)
        self.client = boto3.client('bedrock-runtime', region_name=self.region)
        self.system_prompt = system_prompt
        self.messages = []
        self.tools = None
        self.response_output_tags = []  # Optional tags to extract content, e.g. ['<response>', '</response>']
        self.current_stop_reason = ""  # Store the last stop reason
        self.accumulated_tool_results = []  # Store all tool results for the current conversation turn

    async def invoke_with_prompt(self, prompt):
        """
        Process a text prompt and get a response from the model.
        
        Args:
            prompt (str): User's text prompt
            
        Returns:
            str: Model's response text
        """
        content = [
            {
                'text': prompt
            }
        ]
        return await self.invoke(content)

    async def invoke(self, content):
        """
        Process content and handle the model's response.
        
        Args:
            content (list): List of content items for the model
            
        Returns:
            str: Processed model response
        """
        # Reset accumulated tool results at the start of a new user message
        if isinstance(content, list) and len(content) > 0 and isinstance(content[0], dict) and 'text' in content[0]:
            # This is a new user message, not a tool result
            self.accumulated_tool_results = []
        
        self.messages.append(
            {
                "role": "user", 
                "content": content
            }
        )
        response = self._get_converse_response()
        return await self._handle_response(response)

    def _get_converse_response(self):
        """
        Call the Bedrock Converse API to get a response.
        
        Returns:
            dict: Raw API response from Bedrock
        """
        response = self.client.converse(
            modelId=self.model_id,
            messages=self.messages,
            system=[
                {
                    "text": self.system_prompt
                }
            ],
            inferenceConfig={
                "maxTokens": 8192,
                "temperature": 0.7,
            },
            toolConfig=self.tools.get_tools()
        )
        return response
    
    async def _handle_response(self, response):
        # Add the response to the conversation history
        self.messages.append(response['output']['message'])

        # Do we need to do anything else?
        stop_reason = response['stopReason']

        if stop_reason in ['end_turn', 'stop_sequence']:
            # Safely extract the text from the nested response structure
            try:
                message = response.get('output', {}).get('message', {})
                content = message.get('content', [])
                text = content[0].get('text', '')
                if hasattr(self, 'response_output_tags') and len(self.response_output_tags) == 2:
                    pattern = f"(?s).*{re.escape(self.response_output_tags[0])}(.*?){re.escape(self.response_output_tags[1])}"
                    match = re.search(pattern, text)
                    if match:
                        return match.group(1)
                return text
            except (KeyError, IndexError):
                return ''

        elif stop_reason == 'tool_use':
            try:
                # Extract tool use details from response
                tool_response = []
                for content_item in response['output']['message']['content']:
                    if 'toolUse' in content_item:
                        tool_request = {
                            "toolUseId": content_item['toolUse']['toolUseId'],
                            "name": content_item['toolUse']['name'],
                            "input": content_item['toolUse']['input']
                        }
                        
                        tool_result = await self.tools.execute_tool(tool_request)
                        tool_response.append({'toolResult': tool_result})
                
                return await self.invoke(tool_response)
                
            except KeyError as e:
                raise ValueError(f"Missing required tool use field: {e}")
            except Exception as e:
                raise ValueError(f"Failed to execute tool: {e}")

        elif stop_reason == 'max_tokens':
            # Hit token limit (this is one way to handle it.)
            await self.invoke_with_prompt('Please continue.')

        else:
            raise ValueError(f"Unknown stop reason: {stop_reason}")