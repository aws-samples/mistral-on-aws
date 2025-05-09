"""
Agent module for interacting with Amazon Bedrock models and handling tools execution.
"""
import boto3
import asyncio
import re
import base64
import os
import requests
import mimetypes
from PIL import Image
from io import BytesIO
from urllib.parse import urlparse
from botocore.config import Config
from botocore.exceptions import ClientError


class BedrockConverseAgent:
    """
    Agent class for interacting with Amazon Bedrock models.
    
    Handles communication with the model, manages conversation context,
    and processes tool invocations from the model's responses.
    """
    def __init__(self, model_id, region, system_prompt='You are a helpful assistant.'):
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
        
    async def _fetch_image_from_url(self, image_url):
        """
        Download and process an image from a URL.
        
        Args:
            image_url (str): URL of the image to download
            
        Returns:
            dict: Dictionary containing image data in base64 and mime type
        """
        try:
            # Validate URL
            parsed_url = urlparse(image_url)
            if not parsed_url.scheme or not parsed_url.netloc:
                raise ValueError(f"Invalid URL: {image_url}")
                
            # Download image
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()  # Raise exception for non-200 status codes
            
            # Get content type from response headers or guess from URL
            content_type = response.headers.get('Content-Type')
            if not content_type or not content_type.startswith('image/'):
                # Try to guess from URL
                content_type, _ = mimetypes.guess_type(image_url)
                if not content_type or not content_type.startswith('image/'):
                    # Default to JPEG if we can't determine
                    content_type = 'image/jpeg'
            
            # Always process the image through PIL to validate and normalize it
            try:
                from PIL import Image
                # Load image to validate it's a proper image
                img = Image.open(BytesIO(response.content))
                
                # Check image dimensions - resize if extremely large
                MAX_SIZE = 4096  # Maximum dimension
                if img.width > MAX_SIZE or img.height > MAX_SIZE:
                    print(f"Image is too large ({img.width}x{img.height}), resizing...")
                    # Calculate new dimensions keeping aspect ratio
                    ratio = min(MAX_SIZE / img.width, MAX_SIZE / img.height)
                    new_width = int(img.width * ratio)
                    new_height = int(img.height * ratio)
                    img = img.resize((new_width, new_height), Image.LANCZOS)
                
                # Verify image format compatibility with Bedrock
                valid_formats = ['jpeg', 'jpg', 'png', 'gif', 'webp']
                
                # Extract format from content_type (e.g., 'image/jpeg' -> 'jpeg')
                detected_format = content_type.split('/')[-1].lower()
                
                # Check if the detected format is supported
                format_supported = any(fmt == detected_format for fmt in valid_formats)
                if not format_supported or detected_format not in ['jpeg', 'jpg', 'png', 'gif', 'webp']:
                    print(f"Converting image to JPEG format for compatibility")
                    # Convert to JPEG (most widely supported format)
                    output = BytesIO()
                    
                    # Convert RGBA to RGB if needed
                    if img.mode == 'RGBA':
                        # Create a white background
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        # Paste the image using the alpha channel as mask
                        background.paste(img, (0, 0), img)
                        img = background
                    
                    # Save as JPEG with moderate quality
                    img.convert('RGB').save(output, format='JPEG', quality=85)
                    image_data = output.getvalue()
                    content_type = 'image/jpeg'
                    detected_format = 'jpeg'
                else:
                    # Still process through PIL to ensure valid image
                    output = BytesIO()
                    if detected_format in ['jpeg', 'jpg']:
                        img.convert('RGB').save(output, format='JPEG', quality=90)
                    elif detected_format == 'png':
                        img.save(output, format='PNG')
                    elif detected_format == 'gif':
                        img.save(output, format='GIF')
                    elif detected_format == 'webp':
                        img.save(output, format='WEBP')
                    image_data = output.getvalue()
                
                print(f"Successfully processed image: {img.width}x{img.height} in {detected_format} format")
                
            except Exception as img_err:
                print(f"Failed to process image: {str(img_err)}")
                # Fall back to original image data
                image_data = response.content
            
            # Return the binary data directly
            return {
                "bytes": image_data,
                "mime_type": content_type
            }
            
        except Exception as e:
            raise ValueError(f"Error processing image URL: {str(e)}")
            
    def _is_image_url(self, text):
        """
        Check if the given text contains an image URL.
        
        Args:
            text (str): Text to check for image URLs
            
        Returns:
            tuple: (bool, str or None) - Whether an image URL was found and the URL if found
        """
        # Simple regex to match common image URLs
        # Match URLs ending with image extensions, possibly followed by query parameters
        image_extensions = r'\.(jpg|jpeg|png|gif|bmp|webp|svg)'
        url_pattern = r'(https?://[^\s]+' + image_extensions + r')(\?[^\s]*)?'
        
        match = re.search(url_pattern, text, re.IGNORECASE)
        if match:
            # Return the full URL including query parameters
            return True, match.group(0)
        return False, None

    async def invoke_with_prompt(self, prompt):
        """
        Process a text prompt and get a response from the model.
        Automatically detects and processes image URLs in the prompt.
        
        Args:
            prompt (str): User's text prompt, may contain image URLs
            
        Returns:
            str: Model's response text
        """
        # Check if the prompt contains an image URL
        has_image, image_url = self._is_image_url(prompt)
        
        if has_image:
            try:
                # Extract the image URL and remove it from the prompt
                # Get text before and after the URL
                parts = prompt.split(image_url, 1)
                text_before = parts[0].strip()
                text_after = parts[1].strip() if len(parts) > 1 else ""
                
                # Clean up any fragments from the URL that might remain
                # Look for common URL query param fragments
                text_after = re.sub(r'^\?[a-z0-9=&]+', '', text_after)
                
                # Remove starting URL fragments that might have been split incorrectly
                text_before = re.sub(r'https?:\/\/[^\s]*$', '', text_before).strip()
                
                # Combine text parts, removing the URL itself
                text_prompt = f"{text_before} {text_after}".strip()
                
                # Check if text appears to be asking about the image
                if not text_prompt:
                    text_prompt = "What's in this image?"
                elif not any(term in text_prompt.lower() for term in ['image', 'picture', 'photo', 'describe']):
                    text_prompt = f"About this image: {text_prompt}"
                
                print(f"Processing image URL: {image_url}")
                # Get image data
                image_data = await self._fetch_image_from_url(image_url)
                
                # Create multimodal content
                content = []
                
                # Add text if any
                if text_prompt:
                    content.append({'text': text_prompt})
                    print(f"Adding text prompt: {text_prompt}")
                
                # Add image
                print("Adding image to request")
                
                # Get format from the processed image
                mime_type = image_data['mime_type'].lower()
                image_format = 'jpeg'  # Default to jpeg
                
                # Determine format from MIME type
                if 'png' in mime_type:
                    image_format = 'png'
                elif 'gif' in mime_type:
                    image_format = 'gif'
                elif 'webp' in mime_type:
                    image_format = 'webp'
                
                # Print image info
                print(f"Using image format: {image_format}")
                
                # Add validation check for image size
                image_size = len(image_data['bytes'])
                if image_size > 3750000:  # 3.75MB limit
                    print(f"Warning: Image is very large ({image_size/1000000:.1f}MB), may exceed API limits")
                
                content.append({
                    'image': {
                        'format': image_format,
                        'source': {
                            'bytes': image_data['bytes']
                        }
                    }
                })
                
                print("Sending multimodal request to model")
                return await self.invoke(content)
            except Exception as e:
                # If image processing fails, fall back to text-only with a warning
                error_msg = f"Warning: Failed to process image URL: {str(e)}"
                print(error_msg)
                
                # Add detailed error information based on exception type
                if isinstance(e, requests.exceptions.RequestException):
                    print(f"Network error: Could not download image from URL {image_url}")
                elif isinstance(e, ValueError) and "Invalid URL" in str(e):
                    print(f"Invalid URL format: {image_url}")
                elif isinstance(e, Exception) and "Parameter validation failed" in str(e):
                    print("API parameter validation error - check model compatibility with multimodal inputs")
                
                # Fall back to text-only
                print("Falling back to text-only prompt")
                content = [{'text': prompt}]
                return await self.invoke(content)
        else:
            # Standard text-only prompt
            content = [{'text': prompt}]
            return await self.invoke(content)

    async def invoke(self, content):
        """
        Process content and handle the model's response.
        
        Args:
            content (list): List of content items for the model
            
        Returns:
            str: Processed model response
        """
        
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
        
        Raises:
            ValueError: If there's an issue with the API call
        """
        try:
            response = self.client.converse(
                modelId=self.model_id,
                messages=self.messages,
                system=[
                    {
                        "text": self.system_prompt
                    }
                ],
                inferenceConfig={
                    "maxTokens": 20000,
                    "temperature": 0.7,
                },
                toolConfig=self.tools.get_tools()
            )
            return response
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', 'Unknown error')
            
            # Handle specific error types
            if error_code == 'ValidationException':
                if 'Invalid image content' in error_message:
                    # Handle image validation errors
                    print(f"Image validation failed: {error_message}")
                    print("Attempting to remove last message with image and retry with text only")
                    
                    # Remove the last message (which had the image)
                    if len(self.messages) > 0:
                        last_message = self.messages.pop()
                        # Extract just the text content if any
                        text_content = None
                        for content_item in last_message.get('content', []):
                            if 'text' in content_item:
                                text_content = content_item['text']
                                break
                        
                        if text_content:
                            # Add back just the text portion
                            self.messages.append({
                                "role": "user",
                                "content": [{"text": text_content}]
                            })
                            print(f"Retrying with text-only message: '{text_content}'")
                            return self.client.converse(
                                modelId=self.model_id,
                                messages=self.messages,
                                system=[{"text": self.system_prompt}],
                                inferenceConfig={"maxTokens": 20000, "temperature": 0.7},
                                toolConfig=self.tools.get_tools()
                            )
            
            # If we can't handle specifically, re-raise with more context
            error_msg = f"Amazon Bedrock API error ({error_code}): {error_message}"
            print(error_msg)
            raise ValueError(error_msg) from e
        except Exception as e:
            # Handle other exceptions
            error_msg = f"Error calling Bedrock API: {str(e)}"
            print(error_msg)
            raise ValueError(error_msg) from e
    
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