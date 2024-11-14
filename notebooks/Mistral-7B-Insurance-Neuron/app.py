import streamlit as st
import boto3
import json
from botocore.exceptions import ClientError

# Load configuration from app-config.json
with open("app-config.json", "r") as config_file:
    config = json.load(config_file)

# Extract configuration variables
sagemaker_region = config["sagemaker_region"]
bedrock_region = config["bedrock_region"]
sagemaker_endpoint_name = config["sagemaker_endpoint_name"]
bedrock_model_id = config["bedrock_model_id"]
sagemaker_model_id = config["sagemaker_model_id"]  # Updated field

# Initialize AWS clients in their respective regions
sagemaker_client = boto3.client("sagemaker-runtime", region_name=sagemaker_region)
bedrock_client = boto3.client("bedrock-runtime", region_name=bedrock_region)

# Streamlit UI
st.title("Insurance Customer Support Chatbot")
st.write("This app uses the Mistral-7b-Insurance model deployed on SageMaker or Bedrock to answer questions about insurance.")

# Model selection
model_choice = st.radio("Select the model to use:", ("SageMaker", "Bedrock"))

# Pre-defined prompts for user selection
predefined_prompts = [
    "Can you help me understand my health insurance benefits?",
    "What does my policy cover if I need to see a specialist?",
    "Are dental treatments covered in my current insurance plan?",
    "How do I file a claim for a recent doctor visit?",
    "Can you explain what deductible means in my policy?",
    "Tell me about insurance and its risks",
    "How can I reduce my monthly insurance premium"
]

# Dropdown for predefined prompts with an option to edit or enter a custom query
selected_prompt = st.selectbox("Choose a question or enter your own:", predefined_prompts)
user_query = st.text_input("Your question:", value=selected_prompt)

# Function to query the model on SageMaker
def query_sagemaker_model(endpoint_name, query):
    payload = {
        "model": sagemaker_model_id,  # Updated model name from config
        "messages": [
            {"role": "system", "content": "You are an expert in customer support for Insurance."},
            {"role": "user", "content": query}  # Send the user query as a string
        ],
        "parameters": {
            "do_sample": True,
            "max_new_tokens": 128,
            "temperature": 0.7,
            "top_k": 50,
            "top_p": 0.95,
        }
    }
    
    try:
        # Send the request to SageMaker endpoint
        response = sagemaker_client.invoke_endpoint(
            EndpointName=endpoint_name,
            ContentType="application/json",
            Body=json.dumps(payload)
        )
        
        # Parse the response
        result = json.loads(response['Body'].read())
        return result['choices'][0]['message']['content']
    
    except ClientError as e:
        st.error(f"An error occurred with SageMaker: {e.response['Error']['Message']}")
        return None

# Function to query the model on Bedrock with streaming
def query_bedrock_model(model_id, query):
    # Set base inference configuration
    inference_config = {
        "temperature": 0.5,  # Adjust temperature as needed
        "maxTokens": 1024,   # Set maximum tokens if you want a longer response
        "topP": 0.95         # This is accepted directly by Bedrock in inferenceConfig
    }
    
    # Additional model-specific fields
    additional_model_fields = {
        "top_k": 200  # Set top_k here, as it’s not part of the core inferenceConfig
    }

    # Attempt to stream the response
    try:
        response = bedrock_client.converse_stream(
            modelId=model_id,
            messages=[
                {
                    "role": "user",
                    "content": [{"text": query}]
                }
            ],
            inferenceConfig=inference_config,
            additionalModelRequestFields=additional_model_fields  # Pass additional fields here
        )

        # Display response incrementally as the stream is received
        full_response = ""  # Collects the full response text
        stream = response.get('stream', [])

        # Streamlit placeholder for updating the response in real-time
        response_placeholder = st.empty()

        for event in stream:
            if 'contentBlockDelta' in event:
                delta_text = event['contentBlockDelta']['delta']['text']
                full_response += delta_text
                response_placeholder.text(full_response)  # Update displayed text in real-time

            # Check for end of message
            if 'messageStop' in event:
                break

        return full_response

    except ClientError as e:
        st.error(f"An error occurred with Bedrock: {e.response['Error']['Message']}")
        return None


# Display the response
if user_query:
    st.write("Querying the model...")
    if model_choice == "SageMaker":
        model_response = query_sagemaker_model(sagemaker_endpoint_name, user_query)
        if model_response:
            st.write("Response from the model:")
            st.write(model_response)        
    else:
        # response will be streamed
        model_response = query_bedrock_model(bedrock_model_id, user_query)
    

