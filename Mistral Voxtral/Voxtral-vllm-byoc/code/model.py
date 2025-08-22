#!/usr/bin/env python3

import json
import logging
import os
import signal
import sys
import time
import base64
import tempfile
import re
import uuid
from typing import Any, Dict, List, Optional, Union

import torch
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global variables
app = FastAPI(title="Voxtral vLLM Inference Server", version="1.1.0")
model_engine = None
model_config = {}
model_loaded = False

# Pydantic models for request validation
class ChatMessage(BaseModel):
    role: str
    content: Union[str, List[Dict[str, Any]]]

class InferenceRequest(BaseModel):
    messages: Optional[List[ChatMessage]] = None
    inputs: Optional[Union[str, Dict[str, Any]]] = None
    parameters: Optional[Dict[str, Any]] = {}
    tools: Optional[List[Dict[str, Any]]] = None

def load_serving_properties() -> Dict[str, Any]:
    """Load configuration from serving.properties file"""
    config = {}
    possible_paths = [
        "/opt/ml/code/serving.properties",
        "/opt/ml/model/serving.properties",
    ]
    
    serving_props_path = None
    for path in possible_paths:
        if os.path.exists(path):
            serving_props_path = path
            break
    
    try:
        if serving_props_path:
            logger.info(f"Loading serving.properties from: {serving_props_path}")
            with open(serving_props_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        config[key.strip()] = value.strip()
        else:
            logger.warning("serving.properties not found, using defaults")
            config = {
                "option.model_id": "mistralai/Voxtral-Small-24B-2507",
                "option.dtype": "bfloat16",
                "option.gpu_memory_utilization": "0.9",
                "option.max_model_len": "32768",
                "option.tensor_parallel_degree": "4",
                "option.tokenizer_mode": "mistral",
                "option.config_format": "mistral",
                "option.load_format": "mistral",
                "option.trust_remote_code": "true"
            }
            logger.info("Using default Voxtral configuration")
    except Exception as e:
        logger.error(f"Error loading serving.properties: {e}")
    
    return config

def initialize_model():
    """Initialize the Voxtral model with vLLM engine"""
    global model_engine, model_config, model_loaded
    
    if model_loaded:
        return True
    
    try:
        logger.info("Initializing Voxtral model with vLLM...")
        
        # Load configuration
        config = load_serving_properties()
        
        # Extract model configuration
        model_id = config.get("option.model_id", "mistralai/Voxtral-Small-24B-2507")
        dtype = config.get("option.dtype", "bfloat16")
        gpu_memory_utilization = float(config.get("option.gpu_memory_utilization", "0.9"))
        max_model_len = int(config.get("option.max_model_len", "32768"))
        tensor_parallel_size = int(config.get("option.tensor_parallel_degree", "4"))
        
        # Voxtral-specific configurations
        tokenizer_mode = config.get("option.tokenizer_mode", "mistral")
        config_format = config.get("option.config_format", "mistral")
        load_format = config.get("option.load_format", "mistral")
        trust_remote_code = config.get("option.trust_remote_code", "true").lower() == "true"
        
        logger.info(f"Loading model: {model_id}")
        
        # Import vLLM components
        from vllm import LLM, SamplingParams
        
        # Initialize vLLM engine
        model_engine = LLM(
            model=model_id,
            dtype=dtype,
            gpu_memory_utilization=gpu_memory_utilization,
            max_model_len=max_model_len,
            tensor_parallel_size=tensor_parallel_size,
            tokenizer_mode=tokenizer_mode,
            config_format=config_format,
            load_format=load_format,
            trust_remote_code=trust_remote_code,
            enforce_eager=False,
            disable_log_stats=False,
        )
        
        # Store configuration
        model_config = {
            "model_id": model_id,
            "tokenizer_mode": tokenizer_mode,
            "config_format": config_format,
            "load_format": load_format,
            "max_model_len": max_model_len,
            "dtype": dtype,
            "gpu_memory_utilization": gpu_memory_utilization,
            "tensor_parallel_size": tensor_parallel_size,
            "trust_remote_code": trust_remote_code
        }
        
        model_loaded = True
        logger.info("✅ Voxtral model loaded successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to load model: {str(e)}")
        model_loaded = False
        return False

def supports_function_calling() -> bool:
    """Check if the current model supports function calling"""
    model_id = model_config.get("model_id", "")
    return "Voxtral-Small-24B-2507" in model_id

def parse_voxtral_tool_calls(text: str) -> Optional[List[Dict[str, Any]]]:
    """
    Parse Voxtral's native [TOOL_CALLS] format and convert to OpenAI format
    """
    try:
        # Look for [TOOL_CALLS] pattern
        tool_calls_pattern = r'\[TOOL_CALLS\]\[(.*?)\]'
        matches = re.findall(tool_calls_pattern, text, re.DOTALL)
        
        if not matches:
            return None
        
        tool_calls = []
        for match in matches:
            try:
                # Parse the JSON inside [TOOL_CALLS][...]
                tool_call_data = json.loads(match)
                
                # Handle both single tool call and array of tool calls
                if isinstance(tool_call_data, dict):
                    tool_call_data = [tool_call_data]
                
                for tool_data in tool_call_data:
                    # Convert to OpenAI format
                    openai_tool_call = {
                        "id": f"call_{uuid.uuid4().hex[:8]}",
                        "type": "function",
                        "function": {
                            "name": tool_data.get("name", ""),
                            "arguments": json.dumps(tool_data.get("arguments", {}))
                        }
                    }
                    tool_calls.append(openai_tool_call)
                    
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse tool call JSON: {match}, error: {e}")
                continue
        
        if tool_calls:
            logger.info(f"Parsed {len(tool_calls)} tool calls from Voxtral format")
            return tool_calls
        
        return None
        
    except Exception as e:
        logger.error(f"Error parsing Voxtral tool calls: {e}")
        return None

def clean_voxtral_tool_calls_from_text(text: str) -> str:
    """Remove [TOOL_CALLS] markers from the generated text"""
    try:
        # Remove [TOOL_CALLS][...] patterns
        cleaned_text = re.sub(r'\[TOOL_CALLS\]\[.*?\]', '', text, flags=re.DOTALL)
        
        # Clean up any extra whitespace
        cleaned_text = cleaned_text.strip()
        
        # If the text is empty after cleaning, provide a default message
        if not cleaned_text:
            cleaned_text = "I'll help you with that."
        
        return cleaned_text
        
    except Exception as e:
        logger.error(f"Error cleaning tool calls from text: {e}")
        return text

def process_audio_content(audio_item: Dict[str, Any]) -> Any:
    """Process audio content and return AudioChunk"""
    try:
        from mistral_common.audio import Audio
        from mistral_common.protocol.instruct.messages import AudioChunk
        import requests
        
        audio_data = None
        
        # Handle different audio input formats
        if "path" in audio_item:
            audio_url = audio_item["path"]
            logger.info(f"Processing audio from URL: {audio_url}")
            
            if audio_url.startswith(('http://', 'https://')):
                response = requests.get(audio_url, stream=True, timeout=30)
                response.raise_for_status()
                audio_data = response.content
            else:
                with open(audio_url, 'rb') as f:
                    audio_data = f.read()
                    
        elif "data" in audio_item:
            base64_data = audio_item["data"]
            if base64_data.startswith('data:'):
                base64_data = base64_data.split(',', 1)[1]
            
            logger.info("Processing base64 encoded audio")
            audio_data = base64.b64decode(base64_data)
            
        else:
            raise ValueError("Audio item must contain 'path' or 'data' field")
        
        if audio_data is None:
            raise ValueError("Failed to retrieve audio data")
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
            tmp_file.write(audio_data)
            tmp_path = tmp_file.name
        
        try:
            # Create AudioChunk
            audio = Audio.from_file(tmp_path, strict=False)
            audio_chunk = AudioChunk.from_audio(audio)
            return audio_chunk
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
    except Exception as e:
        logger.error(f"Failed to process audio content: {e}")
        return None

def format_messages_for_voxtral(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Format messages using mistral_common"""
    try:
        from mistral_common.protocol.instruct.messages import TextChunk, AudioChunk, UserMessage, AssistantMessage
        
        formatted_messages = []
        
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            
            if isinstance(content, str):
                # Simple text message
                if role == "user":
                    msg = UserMessage(content=[TextChunk(text=content)])
                else:
                    msg = AssistantMessage(content=content)
                formatted_messages.append(msg.to_openai())
                
            elif isinstance(content, list):
                # Multimodal content
                chunks = []
                
                for item in content:
                    if isinstance(item, dict):
                        item_type = item.get("type")
                        
                        if item_type == "text":
                            chunks.append(TextChunk(text=item.get("text", "")))
                            
                        elif item_type == "audio":
                            audio_chunk = process_audio_content(item)
                            if audio_chunk:
                                chunks.append(audio_chunk)
                            else:
                                logger.warning("Audio processing failed, skipping")
                                continue
                
                if chunks and role == "user":
                    msg = UserMessage(content=chunks)
                    formatted_messages.append(msg.to_openai())
                    
            else:
                # Fallback
                if role == "user":
                    msg = UserMessage(content=[TextChunk(text=str(content))])
                else:
                    msg = AssistantMessage(content=str(content))
                formatted_messages.append(msg.to_openai())
        
        return formatted_messages
        
    except Exception as e:
        logger.error(f"Error formatting messages: {e}")
        return messages


def generate_response(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate response using direct vLLM engine with proper tool call parsing"""
    global model_engine, model_config
    
    if not model_loaded or model_engine is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    try:
        # Parse input formats - get raw messages first
        raw_messages = None
        if "messages" in request_data and request_data["messages"]:
            raw_messages = request_data["messages"]
        elif "inputs" in request_data:
            inputs = request_data["inputs"]
            if isinstance(inputs, dict) and "messages" in inputs:
                raw_messages = inputs["messages"]
            else:
                raw_messages = [{"role": "user", "content": str(inputs)}]
        else:
            raise HTTPException(status_code=400, detail="Invalid input format")
        
        # Process messages with voxtral formatting
        messages = format_messages_for_voxtral(raw_messages)
        
        # Extract parameters
        temperature = request_data.get("temperature", 0.2)
        top_p = request_data.get("top_p", 0.95)
        max_tokens = request_data.get("max_tokens", 512)
        tools = request_data.get("tools")
        
        # Debug logging
        has_tools = bool(tools)
        model_id = model_config.get("model_id", "unknown")
        supports_fc = supports_function_calling()
        
        logger.info(f"Request: has_tools={has_tools}, model_id={model_id}, supports_fc={supports_fc}")
        
        from vllm import SamplingParams
        
        # Configure sampling parameters
        sampling_params = SamplingParams(
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            stop=None
        )
        
        logger.info("Generating response with vLLM...")
        start_time = time.time()
        
        # For function calling, try vLLM's chat method first (it should handle tools properly)
        if tools and supports_fc:
            logger.info("Function calling detected - trying vLLM chat method first")
            try:
                # Try vLLM's chat method with tools - use OpenAI format directly
                logger.info(f"Calling vLLM chat with {len(tools)} OpenAI format tools")
                
                # vLLM expects tools in OpenAI format, not mistral Tool objects
                outputs = model_engine.chat(messages, sampling_params, tools=tools)
                use_generate_fallback = False
                
            except Exception as e:
                logger.warning(f"vLLM chat method with tools failed: {e}")
                logger.info("Falling back to generate method with tool instructions...")
                use_generate_fallback = True
        else:
            try:
                # Use vLLM's chat method for non-function calls
                outputs = model_engine.chat(messages, sampling_params)
                use_generate_fallback = False
                
            except Exception as e:
                logger.warning(f"vLLM chat method failed: {e}")
                logger.info("Falling back to generate method...")
                use_generate_fallback = True
        
        if use_generate_fallback:
            logger.info("Using generate method with explicit tool instructions...")
            
            # Convert to text prompt
            prompt_parts = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                if isinstance(content, list):
                    text_parts = []
                    for item in content:
                        if isinstance(item, dict):
                            if item.get("type") == "text":
                                text_parts.append(item.get("text", ""))
                            elif "audio" in str(item):
                                text_parts.append("[Audio content provided]")
                    content = " ".join(text_parts) if text_parts else str(content)
                    
                prompt_parts.append(f"{role}: {content}")
            
            # Add tool information to prompt if tools are provided
            if tools and supports_fc:
                tool_descriptions = []
                for tool in tools:
                    if "function" in tool:
                        func = tool["function"]
                        tool_descriptions.append(f"- {func['name']}: {func['description']}")
                        # Add parameter details
                        if "parameters" in func and "properties" in func["parameters"]:
                            for param, details in func["parameters"]["properties"].items():
                                tool_descriptions.append(f"  {param}: {details.get('description', '')}")
                
                if tool_descriptions:
                    # Insert tools before the last user message
                    prompt_parts.append("\n--- AVAILABLE FUNCTIONS ---")
                    prompt_parts.extend(tool_descriptions)
                    prompt_parts.append("\n--- INSTRUCTIONS ---")
                    prompt_parts.append("You have access to the functions listed above.")
                    prompt_parts.append("When the user asks for information that requires a function call, you MUST use the function.")
                    prompt_parts.append("Format your response as: [TOOL_CALLS][{\"name\": \"function_name\", \"arguments\": {\"param\": \"value\"}}]")
                    prompt_parts.append("Do NOT say you cannot access real-time information when functions are available.")
                    prompt_parts.append("--- END INSTRUCTIONS ---\n")
            
            prompt_parts.append("assistant:")
            formatted_prompt = "\n".join(prompt_parts)
            
            logger.info(f"Using generate method with {len(tools) if tools else 0} tools")
            logger.info(f"Prompt (first 500 chars): {formatted_prompt[:500]}...")
            logger.info(f"Prompt (last 200 chars): ...{formatted_prompt[-200:]}")
            outputs = model_engine.generate([formatted_prompt], sampling_params)
        
        generation_time = time.time() - start_time
        
        # Extract generated text
        if hasattr(outputs[0], 'outputs'):
            generated_text = outputs[0].outputs[0].text
            prompt_tokens = len(outputs[0].prompt_token_ids)
            completion_tokens = len(outputs[0].outputs[0].token_ids)
        else:
            generated_text = str(outputs[0])
            prompt_tokens = 0
            completion_tokens = 0
        
        logger.info(f"Generated response in {generation_time:.2f}s")
        logger.info(f"Raw response: {generated_text[:200]}...")
        
        # Parse tool calls from the response
        tool_calls = parse_voxtral_tool_calls(generated_text)
        
        # Clean the text
        clean_text = clean_voxtral_tool_calls_from_text(generated_text)
        
        # Create response message
        message_response = {
            "role": "assistant",
            "content": clean_text
        }
        
        # Add tool calls if present
        if tool_calls:
            message_response["tool_calls"] = tool_calls
            logger.info(f"✅ Found {len(tool_calls)} tool calls")
        
        # Create OpenAI-compatible response
        response = {
            "choices": [
                {
                    "index": 0,
                    "message": message_response,
                    "finish_reason": "tool_calls" if tool_calls else "stop"
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            },
            "model": model_config.get("model_id", "mistralai/Voxtral-Small-24B-2507"),
            "object": "chat.completion",
            "created": int(time.time())
        }
        
        return response
        
    except Exception as e:
        logger.error(f"Error during generation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")

# SageMaker endpoints
@app.get("/ping")
async def health_check():
    """SageMaker health check"""
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy" if model_loaded else "starting",
            "model": model_config.get("model_id", "mistralai/Voxtral-Small-24B-2507"),
            "model_loaded": model_loaded,
            "features": {
                "function_calling": supports_function_calling(),
                "multimodal": True,
                "base64_audio": True,
                "tool_call_parsing": True
            }
        }
    )

@app.post("/invocations")
async def invoke_model(request: Request):
    """SageMaker inference endpoint"""
    try:
        request_data = await request.json()
        logger.info(f"Received inference request")
        
        response = generate_response(request_data)
        return JSONResponse(content=response)
        
    except HTTPException as e:
        logger.error(f"HTTP error: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": {"message": str(e), "type": "internal_server_error"}}
        )

@app.on_event("startup")
async def startup_event():
    """Initialize model on startup"""
    logger.info("🚀 Starting Hybrid Voxtral vLLM Server")
    logger.info("📋 Features:")
    logger.info("   ✅ Direct vLLM engine usage")
    logger.info("   ✅ Proper [TOOL_CALLS] parsing")
    logger.info("   ✅ OpenAI-compatible responses")
    logger.info("   ✅ No separate process issues")
    
    try:
        success = initialize_model()
        if success:
            logger.info("✅ Model initialization completed")
        else:
            logger.warning("⚠️  Model initialization failed")
    except Exception as e:
        logger.error(f"❌ Error during model initialization: {e}")

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"Received signal {signum}. Shutting down...")
    sys.exit(0)

def main():
    """Main entry point"""
    os.environ.setdefault("PYTHONUNBUFFERED", "TRUE")
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    port = int(os.environ.get("SAGEMAKER_BIND_TO_PORT", "8080"))
    host = os.environ.get("SAGEMAKER_BIND_TO_HOST", "0.0.0.0")
    
    logger.info(f"🌐 Starting server on {host}:{port}")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True,
        timeout_keep_alive=60,
        timeout_graceful_shutdown=30
    )

if __name__ == "__main__":
    main()