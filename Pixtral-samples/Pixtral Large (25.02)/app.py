import streamlit as st
import os
from dotenv import load_dotenv
import requests
from PIL import Image
import io
import boto3
import base64
import json
from io import BytesIO

# Load environment variables
load_dotenv()

# Initialize the Bedrock runtime client
bedrock_client = boto3.client(service_name='bedrock-runtime')
model_id = 'mistral.pixtral-large-2502-v1:0'

# App title and description
st.set_page_config(
    page_title="Math Problem Assistant", 
    page_icon="🧮",
    layout="wide"
)

# Initialize session state for chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Add MathJax to render LaTeX
st.markdown("""
<script type="text/javascript">
    window.MathJax = {
        tex: {
            inlineMath: [['$','$'], ['\\\\(','\\\\)']],
            displayMath: [['$$','$$'], ['\\\\[','\\\\]']],
            processEscapes: true,
            processEnvironments: true
        },
        options: {
            skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre']
        }
    };
    document.addEventListener('DOMContentLoaded', function() {
        var script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js';
        script.async = true;
        document.head.appendChild(script);
    });
</script>
""", unsafe_allow_html=True)

st.title("Math Problem Assistant on AWS 🧮")
st.markdown("""
Enter the URL of a math problem image, or click "Try Demo". 
I'll explain the math concepts in simple terms and help you solve it step-by-step!
""")

# Main app interface - provide demo option
if st.button("Try Demo", help="Analyze a vector geometry problem"):
    default_url = "https://www.onlinemathlearning.com/image-files/vector-geometry4.jpg"
    st.session_state.image_url = default_url
    # Set a flag to process the demo image automatically
    st.session_state.process_demo = True

# Determine if we should show URL input or use the default
if "image_url" not in st.session_state:
    st.session_state.image_url = ""
    
if "process_demo" not in st.session_state:
    st.session_state.process_demo = False

# Display text input only if we're not using the demo URL or if it's been cleared
image_url = st.text_input("Image URL", placeholder="Enter the URL of a math problem image", value=st.session_state.image_url, label_visibility="collapsed")
st.session_state.image_url = image_url  # Save any changes to the input

# Process the image if we have a URL (either from input or demo)
if image_url or st.session_state.process_demo:
    # If demo was just clicked, use the default URL
    if st.session_state.process_demo and not image_url:
        image_url = "https://www.onlinemathlearning.com/image-files/vector-geometry4.jpg"
        st.session_state.image_url = image_url
        # Reset the flag after processing
        st.session_state.process_demo = False

# Define a default explanation level (removing sidebar options)
explanation_level = "Intermediate"

# Function to ensure LaTeX is properly rendered
def format_math_content(content):
    # Wrap the content in a div with specific styling
    return f"""
    <div style="overflow-x: auto;">
        {content}
    </div>
    """

# Function to get response from Mistral via AWS Bedrock
def get_math_assistance(image_url, level):
    try:
        # Create prompt based on explanation level
        if level == "Simple":
            detail_instruction = "Use very simple language suitable for beginners."
        elif level == "Intermediate":
            detail_instruction = "Use moderately technical language with some math terminology."
        else:  # Detailed
            detail_instruction = "Provide a comprehensive explanation with proper mathematical terminology."
        
        # System message content (will be prepended to user message)
        system_content = f"""You are a helpful math tutor. When shown a math problem:
1. First explain what the problem is asking in simple terms
2. Identify the mathematical concepts involved
3. Provide a step-by-step approach to solve it without giving away the final answer
4. Offer hints if the problem is particularly challenging
5. {detail_instruction}
6. Always use LaTeX format for mathematical notation, inside $ for inline and $$ for display math.

For example:
- Use $\\overrightarrow{{AM}}$ for vector notation
- Use $x^2 + y^2 = r^2$ for equations
- Use $$\\int_a^b f(x) dx$$ for display equations

Remember: Guide the student through the solving process rather than solving it completely."""
        
        # User text content combined with system instructions
        user_text = f"{system_content}\n\nPlease help me understand and solve this math problem. Explain it simply and guide me through the solution process without giving away the final answer. Use proper LaTeX mathematical notation with $ and $$ delimiters."
        
        # Print debug info to terminal
        print("\n=== DEBUG INFO ===")
        print(f"Image URL: {image_url}")
        print(f"Model: {model_id}")
        print(f"Explanation Level: {level}")
        print("==================\n")
        
        # Download the image and convert to base64
        print("Downloading image and converting to base64...")
        response = requests.get(image_url)
        response.raise_for_status()
        
        image_bytes = BytesIO(response.content).read()
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        
        # Create the request payload for Mistral using AWS Bedrock format
        payload = {
            "max_tokens": 2000,
            "temperature": 0.2,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": user_text
                        },
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": base64_image
                            }
                        }
                    ]
                }
            ]
        }
        
        # Convert payload to JSON
        request_body = json.dumps(payload)
        
        # Invoke the model with the invoke_model method
        response = bedrock_client.invoke_model(
            modelId=model_id,
            body=request_body,
            accept="application/json",
            contentType="application/json"
        )
        
        # Parse the response
        response_body = json.loads(response.get("body").read())
        
        # Extract the content based on the response structure
        if "content" in response_body and len(response_body["content"]) > 0:
            response_content = response_body["content"][0]["text"]
        else:
            # Fallback for older response format
            response_content = response_body.get("completion", "")
        
        # Store the conversation in session state - keep system prompt separate for our internal tracking
        st.session_state.messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": "Please help me understand and solve this math problem (image provided). Explain it simply and guide me through the solution process without giving away the final answer."},
            {"role": "assistant", "content": response_content}
        ]
        
        # Save the image URL for future API calls
        st.session_state.current_image_url = image_url
        
        return response_content
        
    except Exception as e:
        import traceback
        print(f"\n=== ERROR ===\n{str(e)}\n{traceback.format_exc()}\n=============\n")
        return f"Error processing request: {str(e)}"

# Function for follow-up chat with the model
def chat_with_model(user_question):
    try:
        # Download the image again and convert to base64
        print("Downloading image again for follow-up...")
        response = requests.get(st.session_state.current_image_url)
        response.raise_for_status()
        
        image_bytes = BytesIO(response.content).read()
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        
        # System message (for our internal tracking only)
        system_message = st.session_state.messages[0]["content"]
        
        # Print debug info to terminal
        print("\n=== FOLLOW-UP QUESTION ===")
        print(f"Question: {user_question}")
        print("=========================\n")
        
        # Build the conversation history for the model in AWS Bedrock format
        conversation_messages = []
        
        # Add initial user message with system instructions and image
        first_user_text = f"{system_message}\n\nPlease help me understand and solve this math problem. Explain it simply and guide me through the solution process without giving away the final answer. Use proper LaTeX mathematical notation with $ and $$ delimiters."
        
        conversation_messages.append({
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": first_user_text
                },
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": base64_image
                    }
                }
            ]
        })
        
        # Add assistant's first response
        conversation_messages.append({
            "role": "assistant",
            "content": st.session_state.messages[2]["content"]
        })
        
        # Add the conversation history (except the initial 3 messages)
        for i in range(3, len(st.session_state.messages)):
            message = st.session_state.messages[i]
            conversation_messages.append({
                "role": message["role"],
                "content": message["content"]
            })
        
        # Add the new user question
        conversation_messages.append({
            "role": "user",
            "content": user_question
        })
        
        # Create the request payload for the model
        payload = {
            "max_tokens": 2000,
            "temperature": 0.2,
            "messages": conversation_messages
        }
        
        # Convert payload to JSON
        request_body = json.dumps(payload)
        
        # Invoke the model
        response = bedrock_client.invoke_model(
            modelId=model_id,
            body=request_body,
            accept="application/json",
            contentType="application/json"
        )
        
        # Parse the response
        response_body = json.loads(response.get("body").read())
        
        # Extract the content based on the response structure
        if "content" in response_body and len(response_body["content"]) > 0:
            response_content = response_body["content"][0]["text"]
        else:
            # Fallback for older response format
            response_content = response_body.get("completion", "")
        
        return response_content
        
    except Exception as e:
        import traceback
        print(f"\n=== ERROR ===\n{str(e)}\n{traceback.format_exc()}\n=============\n")
        return f"Error processing request: {str(e)}"

# Function to fetch and display image from URL
def display_image_from_url(url):
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        image = Image.open(io.BytesIO(response.content))
        st.image(image, use_column_width=True)
        return True
    except Exception as e:
        st.error(f"Could not load image from URL: {str(e)}")
        return False

if image_url:
    # Display the image from URL
    image_loaded = display_image_from_url(image_url)
    
    if image_loaded:
        # Create a placeholder for the spinner
        analysis_placeholder = st.empty()
        
        # Check if this URL has been processed before
        if "last_image_url" not in st.session_state or st.session_state.last_image_url != image_url:
            with analysis_placeholder.container():
                with st.spinner("Processing your math problem..."):
                    # Get math assistance
                    response = get_math_assistance(image_url, explanation_level)
                    
                    # Store response and URL in session state
                    st.session_state.math_assistance = response
                    st.session_state.last_image_url = image_url
                    
                    # Clear any previous chat messages beyond the initial explanation
                    if len(st.session_state.messages) > 3:
                        st.session_state.messages = st.session_state.messages[:3]

# Display initial math assistance (if available)
if "math_assistance" in st.session_state:
    # Remove header - let content speak for itself
    formatted_content = format_math_content(st.session_state.math_assistance)
    st.markdown(formatted_content, unsafe_allow_html=True)
    
    # Add a subtle separator instead of a header
    st.markdown("---")
    
    # Display chat history (skipping the first three messages which are the initial setup)
    for i in range(3, len(st.session_state.messages)):
        message = st.session_state.messages[i]
        with st.chat_message(message["role"]):
            if message["role"] == "assistant":
                formatted_message = format_math_content(message["content"])
                st.markdown(formatted_message, unsafe_allow_html=True)
            else:
                st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask a follow-up question about this math problem..."):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Get and display assistant response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = chat_with_model(prompt)
                formatted_response = format_math_content(response)
                st.markdown(formatted_response, unsafe_allow_html=True)
                
                # Add assistant response to chat history
                st.session_state.messages.append({"role": "assistant", "content": response})

        

        