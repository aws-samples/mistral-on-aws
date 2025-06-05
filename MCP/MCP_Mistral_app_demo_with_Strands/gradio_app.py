"""
Interactive Gradio application that connects Amazon Bedrock with MCP tools.

This module provides a web interface where users can interact with AI models
from Amazon Bedrock while giving the models access to external tools via
the Model Context Protocol (MCP).
"""
import asyncio
import gradio as gr
from datetime import datetime
import logging
import sys
from contextlib import ExitStack
import json
from PIL import Image
import base64
import io

# Import the same libraries as chat.py
from strands import Agent
from strands.tools.mcp import MCPClient
from strands.models import BedrockModel
from mcp import stdio_client, StdioServerParameters
from server_configs import SERVER_CONFIGS
from config import AWS_CONFIG

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("gradio-app")

# Global variables
agent = None
mcp_clients = []
tools = []
exit_stack = None
tool_usage_history = []

def initialize_agent():
    """Initialize Bedrock agent and connect to MCP tools (synchronous version)"""
    global agent, mcp_clients, tools, exit_stack
    
    try:
        # Initialize model configuration from config.py
        model_id = AWS_CONFIG["model_id"]
        
        bedrock_model = BedrockModel(
            model_id=model_id,
            streaming=False
        )
        
        # Define the agent's behavior through system prompt
        system_prompt = """
        You are a helpful assistant that can use tools to help you answer questions and perform tasks.
        You can analyze images and text. When provided with images, describe what you see and answer any questions about the content.
        Please remember and save user's preferences into memory based on user questions and conversations.
        """
        
        # Import server configs 
        server_configs = SERVER_CONFIGS
        mcp_clients = [
            MCPClient(lambda cfg=server_config: stdio_client(cfg))
            for server_config in server_configs
        ]
        
        # Use ExitStack to manage MCP clients
        exit_stack = ExitStack()
        
        # Enter all MCP clients and keep them active
        for mcp_client in mcp_clients:
            exit_stack.enter_context(mcp_client)
        
        # Get tools from all clients
        tools = []
        for i, mcp_client in enumerate(mcp_clients):
            try:
                client_tools = mcp_client.list_tools_sync()
                tools.extend(client_tools)
                logger.info(f"Loaded {len(client_tools)} tools from client {i+1}")
            except Exception as e:
                logger.error(f"Error getting tools from MCP client {i+1}: {e}")
        
        # Create the agent
        agent = Agent(model=bedrock_model, tools=tools, system_prompt=system_prompt)
        logger.info(f"Agent created successfully with {len(tools)} tools")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize agent: {e}")
        return False

def get_available_tools():
    """Get list of available tools for display"""
    global tools
    if not tools:
        return "No tools available yet."
    
    html = "<h3>Available Tools</h3>"
    for tool in tools:
        try:
            tool_spec = tool.tool_spec
            name = tool_spec.get('name', 'Unknown Tool')
            description = tool_spec.get('description', 'No description available')
            
            html += f"""
            <div style="border: 1px solid #ddd; margin-bottom: 10px; padding: 10px; border-radius: 5px;">
                <div style="font-weight: bold; color: #2C3E50;">{name}</div>
                <div style="margin-top: 5px;">{description}</div>
            </div>
            """
        except Exception as e:
            logger.error(f"Error displaying tool: {str(e)}")
            html += f"""
            <div style="border: 1px solid #ddd; margin-bottom: 10px; padding: 10px; border-radius: 5px; color: red;">
                <div>Error displaying tool: {str(e)}</div>
            </div>
            """
    
    return html


def convert_image_to_bytes(image):
    """Convert PIL Image to bytes for Bedrock message format"""
    if image is None:
        return None
    
    try:
        # Convert PIL Image to bytes
        buffered = io.BytesIO()
        # Determine format based on image
        format_type = image.format if image.format else 'PNG'
        if format_type not in ['PNG', 'JPEG', 'JPG']:
            format_type = 'PNG'
        
        image.save(buffered, format=format_type)
        image_bytes = buffered.getvalue()
        
        return {
            'bytes': image_bytes,
            'format': format_type.lower()
        }
    except Exception as e:
        logger.error(f"Error converting image to bytes: {e}")
        return None


def process_message(message, image=None):
    """Process a message from the user and get a response from the agent"""
    global agent, tools
    
    if agent is None:
        # First-time initialization
        if not initialize_agent():
            return "Error: Failed to initialize the agent. Please check the logs."
    
    try:
        # Handle image input by appending message to agent
        if image is not None:
            # Convert image to bytes
            image_data = convert_image_to_bytes(image)
            if image_data:
                # Create message with image and text content
                new_message = {
                    "role": "user",
                    "content": [
                        {
                            "image": {
                                "format": image_data['format'],
                                "source": {
                                    "bytes": image_data['bytes']
                                }
                            }
                        },
                        {
                            "text": message if message.strip() else "Please analyze the content of the image."
                        }
                    ]
                }
                
                # Append the new message to the agent's messages
                agent.messages.append(new_message)
                
                # Get response from agent
                response = agent(message)
            else:
                # Fallback to text-only if image conversion failed
                response = agent(message)
        else:
            # Text-only message
            response = agent(message)
        
        
        # Extract the text content from the agent result
        if hasattr(response, 'text'):
            display_response = response.text
        elif hasattr(response, 'content'):
            display_response = response.content
        else:
            # Fallback to string representation
            display_response = str(response)
        
        return display_response
        
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        import traceback
        traceback.print_exc()
        return f"I encountered an error: {str(e)}"

def reset_conversation():
    """Reset conversation history"""
    global agent, tool_usage_history
    tool_usage_history = []
    return [], "Conversation has been reset."

def respond(message, chat_history, image=None):
    """Process the message and update the chat history"""
    if not message.strip() and image is None:
        return chat_history, "", None
    
    # Create user message content
    user_content = message
    if image is not None:
        user_content += " [Image uploaded]"
    
    # Add user message to history
    chat_history.append({"role": "user", "content": user_content})
    
    # Process user message with image
    bot_response = process_message(message, image)
    
    # Add assistant response to history
    chat_history.append({"role": "assistant", "content": bot_response})
    
    return chat_history, "", None  # Return empty message and clear image

# Create the Gradio interface
with gr.Blocks(css="""
    .container {
        max-width: 1200px;
        margin: auto;
    }
    .tools-panel {
        background-color: #f9f9f9;
        border-radius: 10px;
        padding: 15px;
        margin-top: 15px;
    }
""", title="MCP Application Demo with Mistral Models on Amazon Bedrock") as demo:
    
    gr.HTML("""
        <div style="text-align: center; margin-bottom: 1rem">
            <h1>🤖 MCP Application Demo with Mistral Models on Amazon Bedrock</h1>
            <p>Chat with AI powered by Mistral models on Amazon Bedrock and MCP tools</p>
        </div>
    """)
    
    with gr.Row():
        with gr.Column(scale=2):
            # Chat interface
            chatbot = gr.Chatbot(
                height=500,
                show_label=False,
                container=True,
                show_copy_button=True,
                type="messages"
            )
            
            with gr.Row():
                with gr.Column(scale=6):
                    msg = gr.Textbox(
                        placeholder="Type your message here...",
                        show_label=False,
                        container=False
                    )
                with gr.Column(scale=3):
                    img_input = gr.Image(
                        type="pil",
                        label="Upload Image",
                        sources=["upload", "clipboard"],
                    )
                submit = gr.Button("Send", scale=1, variant="primary")
            
            with gr.Row():
                clear = gr.Button("Clear Chat", variant="secondary")
        
        with gr.Column(scale=1):
            # Tools panel with tabs
            with gr.Tab("Available Tools"):
                tools_display = gr.HTML(
                    value=get_available_tools,
                    show_label=False
                )
                refresh_tools = gr.Button("Refresh Tools", size="sm")
            
            with gr.Tab("Configuration"):
                gr.Markdown("### Current Configuration")
                with gr.Group():
                    gr.Textbox(
                        label="AWS Region",
                        value=AWS_CONFIG["region"],
                        interactive=False
                    )
                    gr.Textbox(
                        label="Model ID", 
                        value=AWS_CONFIG["model_id"],
                        interactive=False
                    )
                    gr.Markdown("*To change configuration, edit config.py and restart*")
    
    # Event handlers
    msg.submit(
        fn=respond,
        inputs=[msg, chatbot, img_input],
        outputs=[chatbot, msg, img_input]
    ).then(
        fn=get_available_tools,
        inputs=None,
        outputs=tools_display
    )
    
    submit.click(
        fn=respond,
        inputs=[msg, chatbot, img_input], 
        outputs=[chatbot, msg, img_input]
    ).then(
        fn=get_available_tools,
        inputs=None,
        outputs=tools_display
    )
    
    clear.click(
        fn=reset_conversation,
        inputs=None,
        outputs=[chatbot, gr.Textbox()]
    )
    
    refresh_tools.click(
        fn=get_available_tools,
        inputs=None,
        outputs=tools_display
    )

if __name__ == "__main__":
    try:
        # Initialize the agent on startup
        logger.info("Starting Gradio application...")
        
        # Launch the Gradio app
        demo.queue()
        demo.launch(
            share=True,
            server_name="0.0.0.0",
            server_port=7860,
            show_error=True
        )
        
    except KeyboardInterrupt:
        logger.info("Application terminated by user.")
    except Exception as e:
        logger.error(f"Application error: {e}")
    finally:
        # Clean up resources
        if exit_stack:
            try:
                exit_stack.close()
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")