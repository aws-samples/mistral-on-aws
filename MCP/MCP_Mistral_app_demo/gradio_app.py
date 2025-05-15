"""
Interactive Gradio application that connects Amazon Bedrock with MCP tools.

This module provides a web interface where users can interact with AI models
from Amazon Bedrock while giving the models access to external tools via
the Model Context Protocol (MCP).
"""
import asyncio
import nest_asyncio
import gradio as gr
from datetime import datetime
from mcp import StdioServerParameters
import logging
import sys
import json

# Import custom modules
from src.agent import BedrockConverseAgent
from src.utility import UtilityHelper
from src.mcpclient import MCPClient
from src.server_configs import SERVER_CONFIGS
from src.config import AWS_CONFIG

# Apply nest_asyncio to allow asyncio within Gradio
nest_asyncio.apply()

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("gradio-app")

# Initialize message history
message_history = []
tool_usage_history = []

# Initialize the agent and tool manager
async def initialize_agent():
    """Initialize Bedrock agent and connect to MCP tools"""
    # Initialize model configuration from config.py
    model_id = AWS_CONFIG["model_id"]
    region = AWS_CONFIG["region"]
    
    # Set up the agent and tool manager
    agent = BedrockConverseAgent(model_id, region)
    utility_manager = UtilityHelper()
    agent.tools = utility_manager

    # Define the agent's behavior through system prompt
    agent.system_prompt = """
    You are a helpful assistant that can use tools to help you answer questions and perform tasks.
    Please remember and save user's preferences into memory based on user questions and conversations.
    """
    
    # Function to handle connection to a single MCP server
    async def setup_mcp_client(server_param):
        """Set up connection to an MCP server and register its tools."""
        try:
            mcp_client = MCPClient(server_param)
            await mcp_client.__aenter__()  # manually enter async context
            tools = await mcp_client.get_available_tools()
        
            for tool in tools:
                agent.tools.register_tool(
                    name=tool['name'],
                    func=mcp_client.call_tool,
                    description=tool['description'],
                    input_schema={'json': tool['inputSchema']}
                )

            return mcp_client
        except Exception as e:
            logger.error(f"Error setting up MCP client: {e}")
            return None

    # Start all MCP clients and register their tools
    mcp_clients = await asyncio.gather(*(setup_mcp_client(cfg) for cfg in SERVER_CONFIGS))
    
    # Filter out any None values from failed client setups
    mcp_clients = [client for client in mcp_clients if client is not None]
    
    # Register a callback for tool usage tracking
    def record_tool_usage(event_data):
        tool_usage_history.append(event_data)
        
    agent.tools.register_tool_usage_callback(record_tool_usage)
    
    # Return the initialized agent and clients
    return agent, mcp_clients, [tool['toolSpec'] for tool in agent.tools.get_tools()['tools']]

# Initialize the agent and client globally
agent = None
mcp_clients = None
available_tools = []

def format_timestamp():
    """Return current time as formatted string"""
    return datetime.now().strftime("%H:%M:%S")

# Process the incoming message
async def process_message(message, history):
    """Process a message from the user and get a response from the agent"""
    global agent
    
    if agent is None:
        # First-time initialization
        global mcp_clients, available_tools
        agent, mcp_clients, available_tools = await initialize_agent()
        
    try:
        # Process message and get response
        # logger.info(f"Processing user message: {message[:50]}...")
        response = await agent.invoke_with_prompt(message)
        # logger.info(f"Generated response of length: {len(response)}")
        
        # Update the tool usage HTML
        get_tool_usage_html()
        
        # Return the response
        return response
        
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        return f"I encountered an error: {str(e)}"

# Function to display tool usage
def get_tool_usage_html():
    """Generate HTML to display tool usage history"""
    if not tool_usage_history:
        return "No tools have been used yet."
    
    html = "<h3>Recent Tool Usage</h3>"
    
    # Group by tool usage events
    current_tool = None
    for event in tool_usage_history[-10:]:
        if event['event'] == 'tool_start':
            tool_name = event['tool_name']
            current_tool = tool_name
            input_data = str(event['input'])
            if len(input_data) > 100:
                input_data = input_data[:100] + "..."
            
            html += f"""
            <div style="border: 1px solid #ddd; margin-bottom: 10px; padding: 10px; border-radius: 5px;">
                <div style="font-weight: bold; color: #2C3E50;">{tool_name}</div>
                <div style="margin-top: 5px;"><strong>Input:</strong> <pre style="background-color: #f9f9f9; padding: 5px; border-radius: 3px;">{input_data}</pre></div>
            """
            
        elif event['event'] == 'tool_complete' and event['tool_name'] == current_tool:
            server_name = event['tool_info']['server_name']
            exec_time = event['tool_info']['execution_time']
            
            html += f"""
                <div style="margin-top: 5px;">
                    <strong>Server:</strong> <span style="color: #16A085;">{server_name}</span>
                </div>
                <div style="margin-top: 5px;">
                    <strong>Execution time:</strong> {exec_time}
                </div>
                <div style="text-align: right; color: green;">✓ Completed</div>
            </div>
            """
            current_tool = None
            
        elif event['event'] == 'tool_error' and event['tool_name'] == current_tool:
            error = event['error']
            
            html += f"""
                <div style="margin-top: 5px;">
                    <strong>Error:</strong> <span style="color: red;">{error}</span>
                </div>
                <div style="text-align: right; color: red;">✗ Failed</div>
            </div>
            """
            current_tool = None
    
    return html

def list_tools():
    """Generate a formatted list of available tools"""
    global available_tools
    if not available_tools:
        return "No tools available yet."
    
    html = "<h3>Available Tools</h3>"
    for tool in available_tools:
        name = tool['name']
        description = tool['description']
        html += f"""
        <div style="border: 1px solid #ddd; margin-bottom: 10px; padding: 10px; border-radius: 5px;">
            <div style="font-weight: bold; color: #2C3E50;">{name}</div>
            <div style="margin-top: 5px;">{description}</div>
        </div>
        """
    return html

# Reset conversation history
def reset_conversation():
    global agent, message_history, tool_usage_history
    if agent:
        agent.messages = []
    message_history = []
    tool_usage_history = []
    return None, "Conversation has been reset."

# Define the chat function that will be used by the interface
def chat(message, chat_history):
    chat_history.append((message, ""))
    return "", chat_history

# Create the Gradio interface
with gr.Blocks(css="""
    .container {
        max-width: 900px;
        margin: auto;
    }
    .tools-panel {
        background-color: #f9f9f9;
        border-radius: 10px;
        padding: 15px;
        margin-top: 15px;
    }
""") as demo:
    with gr.Row():
        gr.HTML("""
            <div style="text-align: center; margin-bottom: 1rem">
                <h1>MCP Application Demo</h1>
                <p>Ask questions and get help with tasks using MCP servers</p>
            </div>
        """)
    
    with gr.Row():
        with gr.Column(scale=2):
            chatbot = gr.Chatbot(
                value=[],
                elem_id="chatbot",
                height=500,
                show_label=False,
                type="messages"  # Use the modern format
            )
            
            with gr.Row():
                msg = gr.Textbox(
                    placeholder="Type your message here...",
                    show_label=False,
                    container=False,
                    scale=8
                )
                submit = gr.Button("Send", scale=1)
            
            reset_btn = gr.Button("Reset Conversation")
            
        with gr.Column(scale=1):
            with gr.Tab("Tool Usage"):
                tool_usage = gr.HTML(get_tool_usage_html)
            with gr.Tab("Available Tools"):
                tools_list = gr.HTML(list_tools)
            with gr.Tab("Configuration"):
                gr.Markdown("### AWS Bedrock Configuration")
                region_input = gr.Textbox(
                    label="AWS Region",
                    value=AWS_CONFIG["region"],
                    placeholder="e.g., us-east-1, eu-central-1"
                )
                model_id_input = gr.Textbox(
                    label="Model ID",
                    value=AWS_CONFIG["model_id"],
                    placeholder="e.g., us.anthropic.claude-3-sonnet-20240229-v1:0"
                )
                update_config_btn = gr.Button("Update Configuration")
    
    # Set up the chat functionality
    async def respond(message, chat_history):
        """Process the message and update the chat history"""
        global agent, mcp_clients, available_tools
        if not message.strip():
            return chat_history
            
        # Add user message to history
        chat_history.append({"role": "user", "content": message})
        
        # Initialize agent if needed
        if agent is None:
            agent, mcp_clients, available_tools = await initialize_agent()
        
        # Process user message
        bot_response = await process_message(message, chat_history)
        
        # Add assistant message to history
        chat_history.append({"role": "assistant", "content": bot_response})
        
        # Update tool usage display
        return chat_history
    
    # Handle message submission
    msg.submit(
        fn=respond, 
        inputs=[msg, chatbot], 
        outputs=[chatbot]
    ).then(
        fn=lambda: "", 
        inputs=None, 
        outputs=msg
    ).then(
        fn=get_tool_usage_html,
        inputs=None,
        outputs=tool_usage
    )
    
    # Also handle the send button click
    submit.click(
        fn=respond, 
        inputs=[msg, chatbot], 
        outputs=[chatbot]
    ).then(
        fn=lambda: "", 
        inputs=None, 
        outputs=msg
    ).then(
        fn=get_tool_usage_html,
        inputs=None,
        outputs=tool_usage
    )
    
    # Handle reset button
    # Function to reset agent messages
    def reset_agent_messages():
        global agent
        if agent:
            agent.messages = []
        return None
    
    # Function to update AWS configuration
    def update_config(region, model_id):
        global agent, AWS_CONFIG
        # Update the configuration
        AWS_CONFIG["region"] = region
        AWS_CONFIG["model_id"] = model_id
        
        # Reset the agent so it will be reinitialized with new settings
        agent = None
        
        # Write the updated configuration to the file
        try:
            with open('/Users/hoying/Documents/2025/MCP/blog_code/src/config.py', 'w') as f:
                f.write('"""\nConfiguration module for the MCP application.\n\n')
                f.write('This module stores configuration parameters for the application, such as\n')
                f.write('AWS region and model ID for Amazon Bedrock service.\n"""\n\n')
                f.write('# AWS Bedrock configuration\n')
                f.write('AWS_CONFIG = {\n')
                f.write(f'    "region": "{region}",  # AWS region\n')
                f.write(f'    "model_id": "{model_id}"  # Model ID\n')
                f.write('}')
            
            return f"Configuration updated successfully. Region: {region}, Model ID: {model_id}"
        except Exception as e:
            return f"Error updating configuration: {str(e)}"
        
    reset_btn.click(
        fn=lambda: ([], "Conversation has been reset."), 
        inputs=None, 
        outputs=[chatbot, tool_usage]
    ).then(
        fn=reset_agent_messages, 
        inputs=None, 
        outputs=None
    )
    
    # Handle configuration update button
    update_config_btn.click(
        fn=update_config,
        inputs=[region_input, model_id_input],
        outputs=gr.Textbox(label="Status")
    )

if __name__ == "__main__":
    import os
    
    try:
        # Start the Gradio app
        demo.queue()
        
        # # Get port from environment or use none to auto-select an available port
        # port = os.environ.get("GRADIO_SERVER_PORT", None)
        # port = int(port) if port is not None else None
        
        # demo.launch(
        #     share=True,      # Only share if explicitly enabled
        #     server_name="0.0.0.0",   # Listen on all interfaces
        #     server_port=8080         # Auto-select an available port
        # )
        demo.launch(share=True)
    except KeyboardInterrupt:
        # Clean up resources on keyboard interrupt
        if mcp_clients:
            asyncio.run(asyncio.gather(*[client.cleanup() for client in mcp_clients if client]))
        print("\nApplication terminated by user.")
    except Exception as e:
        print(f"Application error: {e}")