#!/usr/bin/env python3

import json
import logging
import os
import signal
import sys
import time
import base64
import tempfile
import subprocess
import threading
import requests
import re
import random
from typing import Any, Dict, List, Optional, Union
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from openai import OpenAI

# Import Mistral Common for audio processing and tool calling
try:
    from mistral_common.protocol.transcription.request import TranscriptionRequest
    from mistral_common.protocol.instruct.messages import RawAudio, TextChunk, AudioChunk, UserMessage, AssistantMessage
    from mistral_common.protocol.instruct.tool_calls import Function, Tool
    from mistral_common.audio import Audio
    MISTRAL_AVAILABLE = True
except ImportError:
    MISTRAL_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Global variables
vllm_server_process = None
openai_client = None
model_config = {}
model_loaded = False
server_ready = False

# Configuration constants 
MAX_AUDIO_SIZE_MB = 50  # 50MB limit for audio files
MAX_AUDIO_SIZE_BYTES = MAX_AUDIO_SIZE_MB * 1024 * 1024


# Pydantic models for request validation
class ChatMessage(BaseModel):
    role: str
    content: Union[str, List[Dict[str, Any]]]

class TranscriptionRequest(BaseModel):
    audio: Union[str, Dict[str, Any]]
    language: Optional[str] = "en"
    temperature: Optional[float] = 0.0
    model: Optional[str] = None

class InferenceRequest(BaseModel):
    messages: Optional[List[ChatMessage]] = None
    inputs: Optional[Union[str, Dict[str, Any]]] = None
    parameters: Optional[Dict[str, Any]] = {}
    tools: Optional[List[Dict[str, Any]]] = None
    transcription: Optional[TranscriptionRequest] = None

def load_serving_properties() -> Dict[str, Any]:
    """Load configuration from serving.properties file"""
    config = {}
    possible_paths = [
        "/opt/ml/code/serving.properties",
        "/opt/ml/model/serving.properties",
    ]

    for path in possible_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            config[key.strip()] = value.strip()
                break
            except Exception:
                continue

    # Default configuration
    if not config:
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

    return config

def wait_for_server(host: str = "127.0.0.1", port: int = 8000, timeout: int = 300) -> bool:
    """Wait for vLLM OpenAI server to be ready"""
    start_time = time.time()
    health_url = f"http://{host}:{port}/health"

    while time.time() - start_time < timeout:
        try:
            response = requests.get(health_url, timeout=5)
            if response.status_code == 200:
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(2)

    return False

def find_vllm_executable():
    """Find vLLM executable"""
    # Try direct vllm command first
    for vllm_cmd in ["vllm", "/usr/local/bin/vllm", "/opt/conda/bin/vllm"]:
        try:
            result = subprocess.run([vllm_cmd, "--help"], capture_output=True, timeout=10)
            if result.returncode == 0:
                return ("direct", vllm_cmd)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

    # Try Python module approach
    for py_cmd in ["python3", "python", "/usr/bin/python3", "/usr/local/bin/python3"]:
        try:
            result = subprocess.run([py_cmd, "--version"], capture_output=True, timeout=5)
            if result.returncode == 0:
                test_result = subprocess.run([py_cmd, "-c", "import vllm"], capture_output=True, timeout=10)
                if test_result.returncode == 0:
                    return ("module", py_cmd)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

    return (None, None)

def start_vllm_server():
    """Start vLLM OpenAI-compatible server as a subprocess"""
    global vllm_server_process, server_ready

    try:
        config = load_serving_properties()

        # Extract model configuration
        model_id = config.get("option.model_id", "mistralai/Voxtral-Small-24B-2507")
        dtype = config.get("option.dtype", "bfloat16")
        gpu_memory_utilization = float(config.get("option.gpu_memory_utilization", "0.9"))
        max_model_len = int(config.get("option.max_model_len", "32768"))
        tensor_parallel_size = int(config.get("option.tensor_parallel_degree", "4"))
        tokenizer_mode = config.get("option.tokenizer_mode", "mistral")
        config_format = config.get("option.config_format", "mistral")
        load_format = config.get("option.load_format", "mistral")
        trust_remote_code = config.get("option.trust_remote_code", "true").lower() == "true"

        # Find vLLM executable
        exec_type, exec_cmd = find_vllm_executable()
        if not exec_cmd:
            raise RuntimeError("vLLM not found")

        # Build command based on executable type
        if exec_type == "direct":
            cmd = [
                exec_cmd, "serve", model_id,
                "--dtype", dtype,
                "--gpu-memory-utilization", str(gpu_memory_utilization),
                "--max-model-len", str(max_model_len),
                "--tensor-parallel-size", str(tensor_parallel_size),
                "--tokenizer-mode", tokenizer_mode,
                "--config-format", config_format,
                "--load-format", load_format,
                "--host", "127.0.0.1",
                "--port", "8000",
                "--served-model-name", model_id,
                "--disable-log-requests"
            ]
        else:
            cmd = [
                exec_cmd, "-m", "vllm.entrypoints.openai.api_server",
                "--model", model_id,
                "--dtype", dtype,
                "--gpu-memory-utilization", str(gpu_memory_utilization),
                "--max-model-len", str(max_model_len),
                "--tensor-parallel-size", str(tensor_parallel_size),
                "--tokenizer-mode", tokenizer_mode,
                "--config-format", config_format,
                "--load-format", load_format,
                "--host", "127.0.0.1",
                "--port", "8000",
                "--served-model-name", model_id,
                "--disable-log-requests"
            ]

        if trust_remote_code:
            cmd.append("--trust-remote-code")

        # Set up environment
        vllm_env = os.environ.copy()
        vllm_env.update({
            "PYTHONUNBUFFERED": "1",
            "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES", "0,1,2,3"),
            "VLLM_WORKER_MULTIPROC_METHOD": "spawn",
            "HF_HOME": "/tmp/hf_home",
            "TRANSFORMERS_CACHE": "/tmp/transformers_cache"
        })

        # Start the server process
        vllm_server_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            env=vllm_env,
            preexec_fn=os.setsid
        )

        # Monitor logs in background
        def monitor_logs():
            for line in vllm_server_process.stdout:
                if "ERROR" in line or "CRITICAL" in line:
                    logger.error(f"[vLLM] {line.strip()}")

        log_thread = threading.Thread(target=monitor_logs, daemon=True)
        log_thread.start()

        # Wait for server to be ready
        server_ready = wait_for_server()

        if server_ready:
            global model_config
            model_config = {
                "model_id": model_id,
                "tokenizer_mode": tokenizer_mode,
                "config_format": config_format,
                "load_format": load_format,
                "max_model_len": max_model_len,
                "dtype": dtype,
                "gpu_memory_utilization": gpu_memory_utilization,
                "tensor_parallel_size": tensor_parallel_size,
                "trust_remote_code": trust_remote_code,
                "server_host": "127.0.0.1",
                "server_port": 8000
            }

        return server_ready

    except Exception as e:
        logger.error(f"Failed to start vLLM server: {str(e)}")
        return False

def initialize_openai_client():
    """Initialize OpenAI client to connect to vLLM server"""
    global openai_client, model_loaded

    if not server_ready:
        return False

    try:
        openai_client = OpenAI(api_key="EMPTY", base_url="http://127.0.0.1:8000/v1")
        # Test connection
        models = openai_client.models.list()
        model_loaded = True
        return True
    except Exception:
        model_loaded = False
        return False

def supports_function_calling() -> bool:
    """Check if the current model supports function calling"""
    model_id = model_config.get("model_id", "")
    return "Voxtral-Small-24B-2507" in model_id

def convert_openai_tools_to_mistral(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert OpenAI format tools to Mistral format"""
    if not MISTRAL_AVAILABLE:
        return tools

    try:
        mistral_tools = []
        for tool in tools:
            if tool.get("type") == "function":
                func_info = tool["function"]
                mistral_tool = Tool(
                    function=Function(
                        name=func_info["name"],
                        description=func_info["description"],
                        parameters=func_info.get("parameters", {})
                    )
                )
                openai_tool = mistral_tool.to_openai()
                mistral_tools.append(openai_tool)

        return mistral_tools if mistral_tools else tools
    except Exception:
        return tools

def parse_voxtral_tool_calls(text: str) -> Optional[List[Dict[str, Any]]]:
    """Parse Voxtral's native [TOOL_CALLS] format and convert to OpenAI format"""
    try:
        tool_calls_pattern = r'\[(?:TOOL_CALLS|tool_calls)\]\[(.+?)\](?=\s*$|\s*\w)'
        matches = re.findall(tool_calls_pattern, text, re.DOTALL | re.IGNORECASE)

        if not matches:
            start_pattern = r'\[(?:TOOL_CALLS|tool_calls)\]\['
            match_start = re.search(start_pattern, text, re.IGNORECASE)
            if match_start:
                start_pos = match_start.end()
                bracket_count = 1
                i = start_pos
                while i < len(text) and bracket_count > 0:
                    if text[i] == '[':
                        bracket_count += 1
                    elif text[i] == ']':
                        bracket_count -= 1
                    i += 1
                if bracket_count == 0:
                    json_content = text[start_pos:i-1]
                    matches = [json_content]

        if not matches:
            return None

        tool_calls = []
        for match in matches:
            try:
                tool_call_data = json.loads(match)
                if isinstance(tool_call_data, dict):
                    tool_call_data = [tool_call_data]

                for tool_data in tool_call_data:
                    # tool_call_id = secrets.token_urlsafe(12)  # Generates 16-character secure ID
                    tool_call_id = ''.join(random.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=9))
                    openai_tool_call = {
                        "id": tool_call_id,
                        "type": "function",
                        "function": {
                            "name": tool_data.get("name", ""),
                            "arguments": json.dumps(tool_data.get("arguments", {}))
                        }
                    }
                    tool_calls.append(openai_tool_call)

            except json.JSONDecodeError:
                continue

        return tool_calls if tool_calls else None

    except Exception:
        return None

def clean_voxtral_tool_calls_from_text(text: str) -> str:
    """Remove [TOOL_CALLS] markers from the generated text"""
    try:
        cleaned_text = re.sub(r'\[(?:TOOL_CALLS|tool_calls)\]\[.*?\]', '', text, flags=re.DOTALL | re.IGNORECASE)
        cleaned_text = cleaned_text.strip()
        return cleaned_text if cleaned_text else "I'll help you with that."
    except Exception:
        return text

def validate_audio_url(url: str) -> bool:
    """
    Validate audio URL to prevent SSRF attacks.

    For POC/sample: Blocks AWS metadata endpoint and localhost.
    For production: Add allowlist of approved domains.
    """
    from urllib.parse import urlparse

    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid URL format")

    # Must be HTTPS (allow HTTP for local testing)
    if parsed.scheme not in ['http', 'https']:
        raise HTTPException(status_code=400, detail="Only HTTP/HTTPS URLs supported")

    # Block AWS metadata endpoint (critical!)
    blocked_hosts = [
        '169.254.169.254',  # AWS metadata
        'metadata.google.internal',  # GCP metadata
        '127.0.0.1',
        'localhost',
        '0.0.0.0'
    ]

    hostname = parsed.hostname or ''
    if hostname in blocked_hosts:
        raise HTTPException(
            status_code=400,
            detail=f"Access to {hostname} is not allowed"
        )

    # Block private IP ranges (optional but recommended)
    if hostname.startswith(('10.', '172.16.', '192.168.')):
        raise HTTPException(
            status_code=400,
            detail="Private IP addresses are not allowed"
        )

    return True

def validate_file_path(file_path: str, allowed_base: str = "/opt/ml") -> str:
    """
    Validate file path to prevent path traversal attacks.

    For POC: Restricts to /opt/ml and /tmp directories.
    Adjust allowed_base for your specific requirements.
    """
    import os

    # Resolve to absolute path
    try:
        abs_path = os.path.abspath(file_path)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid file path")

    # Check if path is within allowed directories
    allowed_prefixes = [
        os.path.abspath(allowed_base),
        os.path.abspath("/tmp")
    ]

    if not any(abs_path.startswith(prefix) for prefix in allowed_prefixes):
        raise HTTPException(
            status_code=400,
            detail=f"File access restricted to allowed directories"
        )

    # Additional safety checks
    if ".." in file_path or file_path.startswith("/etc/"):
        raise HTTPException(status_code=400, detail="Invalid file path")

    return abs_path

def validate_audio_size(audio_data: bytes) -> bool:
    """Validate audio file size to prevent DoS via large files."""
    if len(audio_data) > MAX_AUDIO_SIZE_BYTES:
        raise HTTPException(
            status_code=413,  # Payload Too Large
            detail=f"Audio file exceeds maximum size of {MAX_AUDIO_SIZE_MB}MB"
        )
    return True

def load_audio_from_source(audio_source: Union[str, Dict[str, Any]]) -> Optional[Any]:
    """Load audio from various sources and return Audio object"""
    if not MISTRAL_AVAILABLE:
        return None

    try:
        audio_data = None
        temp_file_path = None

        if isinstance(audio_source, str):
            if audio_source.startswith(('http://', 'https://')):
                validate_audio_url(audio_source)  # Add validation
                response = requests.get(audio_source, stream=True, timeout=30)
                response.raise_for_status()
                audio_data = response.content
            elif audio_source.startswith('data:'):
                # Handle data URL format (e.g., data:audio/wav;base64,...)
                base64_data = audio_source.split(',', 1)[1] if ',' in audio_source else audio_source
                audio_data = base64.b64decode(base64_data)
            elif '/' not in audio_source and '\\' not in audio_source:
                # Likely a base64 string (no path separators)
                try:
                    audio_data = base64.b64decode(audio_source)
                except Exception:
                    # If base64 decode fails, treat as file path
                    validated_path = validate_file_path(audio_source)
                    with open(validated_path, 'rb') as f:
                        audio_data = f.read()
            else:
                # Treat as file path
                validated_path = validate_file_path(audio_source)
                with open(validated_path, 'rb') as f:
                    audio_data = f.read()

        elif isinstance(audio_source, dict):
            if "path" in audio_source:
                audio_url = audio_source["path"]
                if audio_url.startswith(('http://', 'https://')):
                    validate_audio_url(audio_url)  # Add validation
                    response = requests.get(audio_url, stream=True, timeout=30)
                    response.raise_for_status()
                    audio_data = response.content
                else:
                    with open(audio_url, 'rb') as f:
                        audio_data = f.read()
            elif "data" in audio_source:
                base64_data = audio_source["data"]
                if base64_data.startswith('data:'):
                    base64_data = base64_data.split(',', 1)[1]
                audio_data = base64.b64decode(base64_data)

        if audio_data is None:
            return None

        # Validate file size
        validate_audio_size(audio_data)

        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
            tmp_file.write(audio_data)
            temp_file_path = tmp_file.name

        audio = Audio.from_file(temp_file_path, strict=False)
        return audio

    except Exception:
        return None
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except:
                pass

def transcribe_audio(audio_source: Union[str, Dict[str, Any]], language: str = "en", temperature: float = 0.0) -> Dict[str, Any]:
    """Transcribe audio using OpenAI client connected to vLLM Voxtral server"""
    if not model_loaded or openai_client is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    if not MISTRAL_AVAILABLE:
        raise HTTPException(status_code=503, detail="mistral_common[audio] not available")

    try:
        start_time = time.time()
        audio = load_audio_from_source(audio_source)
        if audio is None:
            raise HTTPException(status_code=400, detail="Failed to load audio")

        raw_audio = RawAudio.from_audio(audio)
        model_id = model_config.get("model_id", "mistralai/Voxtral-Small-24B-2507")

        from mistral_common.protocol.transcription.request import TranscriptionRequest as MistralTranscriptionRequest

        transcription_req = MistralTranscriptionRequest(
            model=model_id,
            audio=raw_audio,
            language=language,
            temperature=temperature
        ).to_openai(exclude=("top_p", "seed"))

        response = openai_client.audio.transcriptions.create(**transcription_req)
        processing_time = time.time() - start_time

        result = {
            "text": response.text,
            "language": language,
            "duration": audio.duration,
            "processing_time": processing_time,
            "model": model_id
        }

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

def process_audio_content_for_chat(audio_item: Dict[str, Any]) -> Optional[Any]:
    """Process audio content for chat messages"""
    if not MISTRAL_AVAILABLE:
        if "path" in audio_item:
            return f"[Audio file: {audio_item['path']}]"
        else:
            return "[Audio content - cannot process without mistral_common[audio]]"

    try:
        audio_source = None
        if "path" in audio_item:
            audio_source = audio_item["path"]
        elif "data" in audio_item:
            audio_source = {"data": audio_item["data"]}
        else:
            return "[Invalid audio content]"

        audio = load_audio_from_source(audio_source)
        if audio is None:
            return "[Failed to load audio]"

        audio_chunk = AudioChunk.from_audio(audio)
        return audio_chunk

    except Exception:
        if "path" in audio_item:
            return f"[Audio processing failed for: {audio_item['path']}]"
        else:
            return "[Audio processing failed]"

def format_messages_for_openai(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Format messages for OpenAI API with multimodal support"""
    if not MISTRAL_AVAILABLE:
        return format_messages_fallback(messages)

    try:
        formatted_messages = []

        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")

            # Handle tool messages
            if role == "tool":
                tool_message = {
                    "role": "tool",
                    "content": str(content),
                    "tool_call_id": message.get("tool_call_id", "unknown")
                }
                if "name" in message:
                    tool_message["name"] = message["name"]
                formatted_messages.append(tool_message)
                continue

            # Handle assistant messages with tool calls
            if role == "assistant" and "tool_calls" in message:
                formatted_messages.append(message)
                continue

            if isinstance(content, str):
                if role == "user":
                    msg = UserMessage(content=[TextChunk(text=content)])
                    formatted_messages.append(msg.to_openai())
                elif role == "assistant":
                    msg = AssistantMessage(content=content)
                    formatted_messages.append(msg.to_openai())
                else:
                    formatted_messages.append({"role": role, "content": content})

            elif isinstance(content, list):
                chunks = []
                for item in content:
                    if isinstance(item, dict):
                        item_type = item.get("type")
                        if item_type == "text":
                            chunks.append(TextChunk(text=item.get("text", "")))
                        elif item_type == "audio":
                            audio_chunk = process_audio_content_for_chat(item)
                            if isinstance(audio_chunk, str):
                                chunks.append(TextChunk(text=audio_chunk))
                            elif audio_chunk is not None:
                                chunks.append(audio_chunk)

                if chunks and role == "user":
                    msg = UserMessage(content=chunks)
                    formatted_messages.append(msg.to_openai())
                else:
                    text_content = " ".join([
                        chunk.text if hasattr(chunk, 'text') else str(chunk)
                        for chunk in chunks
                    ])
                    formatted_messages.append({"role": role, "content": text_content})

            else:
                if role == "user":
                    msg = UserMessage(content=[TextChunk(text=str(content))])
                    formatted_messages.append(msg.to_openai())
                else:
                    formatted_messages.append({"role": role, "content": str(content)})

        return formatted_messages

    except Exception:
        return format_messages_fallback(messages)

def format_messages_fallback(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Fallback message formatting without mistral_common"""
    formatted_messages = []

    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")

        if role == "tool":
            tool_message = {
                "role": "tool",
                "content": str(content),
                "tool_call_id": message.get("tool_call_id", "unknown")
            }
            if "name" in message:
                tool_message["name"] = message["name"]
            formatted_messages.append(tool_message)
            continue

        if role == "assistant" and "tool_calls" in message:
            formatted_messages.append(message)
            continue

        if isinstance(content, str):
            formatted_messages.append({"role": role, "content": content})
        elif isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict):
                    item_type = item.get("type")
                    if item_type == "text":
                        text_parts.append(item.get("text", ""))
                    elif item_type == "audio":
                        if "path" in item:
                            text_parts.append(f"[Audio file: {item['path']}]")
                        else:
                            text_parts.append("[Audio content]")

            formatted_messages.append({
                "role": role,
                "content": " ".join(text_parts) if text_parts else str(content)
            })
        else:
            formatted_messages.append({"role": role, "content": str(content)})

    return formatted_messages

def generate_response(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate response using OpenAI client connected to vLLM server"""
    if not model_loaded or openai_client is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        # Check if this is a transcription request
        if "transcription" in request_data and request_data["transcription"]:
            transcription_req = request_data["transcription"]
            audio_source = transcription_req.get("audio")
            language = transcription_req.get("language", "en")
            temperature = transcription_req.get("temperature", 0.0)

            if not audio_source:
                raise HTTPException(status_code=400, detail="Audio source required for transcription")

            result = transcribe_audio(audio_source, language, temperature)
            return {
                "transcription": result,
                "model": model_config.get("model_id", "mistralai/Voxtral-Small-24B-2507"),
                "object": "transcription",
                "created": int(time.time())
            }

        # Parse input formats for chat/text generation
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

        # Format messages for OpenAI API
        messages = format_messages_for_openai(raw_messages)

        # Extract parameters
        temperature = request_data.get("temperature", 0.2)
        top_p = request_data.get("top_p", 0.95)
        max_tokens = request_data.get("max_tokens", 1024)
        tools = request_data.get("tools")

        # Prepare request parameters
        request_params = {
            "model": model_config.get("model_id", "mistralai/Voxtral-Small-24B-2507"),
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
        }

        # Add tools if provided and supported
        if tools and supports_function_calling():
            converted_tools = convert_openai_tools_to_mistral(tools)
            request_params["tools"] = converted_tools

        # Make the request to vLLM via OpenAI client
        start_time = time.time()
        response = openai_client.chat.completions.create(**request_params)

        # Convert OpenAI response to our expected format
        choice = response.choices[0]
        raw_content = choice.message.content or ""

        # Check for Voxtral-style tool calls first
        voxtral_tool_calls = None
        if tools and supports_function_calling():
            voxtral_tool_calls = parse_voxtral_tool_calls(raw_content)

        # Clean the content text
        clean_content = clean_voxtral_tool_calls_from_text(raw_content)

        message_response = {
            "role": "assistant",
            "content": clean_content
        }

        # Add tool calls - prioritize Voxtral parsing over OpenAI native
        final_tool_calls = None
        if voxtral_tool_calls:
            final_tool_calls = voxtral_tool_calls
        elif choice.message.tool_calls:
            final_tool_calls = [
                {
                    "id": tool_call.id,
                    "type": tool_call.type,
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments
                    }
                }
                for tool_call in choice.message.tool_calls
            ]

        if final_tool_calls:
            message_response["tool_calls"] = final_tool_calls

        # Determine finish reason
        finish_reason = choice.finish_reason
        if final_tool_calls:
            finish_reason = "tool_calls"

        # Create final response
        final_response = {
            "choices": [
                {
                    "index": 0,
                    "message": message_response,
                    "finish_reason": finish_reason
                }
            ],
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0
            },
            "model": model_config.get("model_id", "mistralai/Voxtral-Small-24B-2507"),
            "object": "chat.completion",
            "created": int(time.time())
        }

        return final_response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")

def shutdown_vllm_server():
    """Gracefully shutdown vLLM server"""
    global vllm_server_process

    if vllm_server_process:
        try:
            os.killpg(os.getpgid(vllm_server_process.pid), signal.SIGTERM)
            try:
                vllm_server_process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(vllm_server_process.pid), signal.SIGKILL)
                vllm_server_process.wait()
        except Exception:
            pass
        finally:
            vllm_server_process = None

# Lifespan manager for FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    server_started = start_vllm_server()
    if server_started:
        client_ready = initialize_openai_client()
        if not client_ready:
            logger.warning("OpenAI client initialization failed")
    else:
        logger.warning("vLLM server initialization failed")

    yield

    # Shutdown
    shutdown_vllm_server()

# Create FastAPI app
app = FastAPI(
    title="Voxtral vLLM OpenAI-Compatible Server",
    version="2.0.0",
    lifespan=lifespan,
    # Limit request body size to prevent DoS
    max_request_size=100 * 1024 * 1024  # 100MB max
)

@app.get("/ping")
async def health_check():
    """SageMaker health check"""
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy" if model_loaded and server_ready else "starting",
            "model": model_config.get("model_id", "mistralai/Voxtral-Small-24B-2507"),
            "model_loaded": model_loaded,
            "server_ready": server_ready,
            "implementation": "openai_client_transcription",
            "features": {
                "transcription": MISTRAL_AVAILABLE,
                "function_calling": supports_function_calling(),
                "multimodal": True,
                "openai_compatible": True,
                "separate_server": True,
                "audio_formats": ["wav", "mp3", "m4a", "flac"] if MISTRAL_AVAILABLE else []
            }
        }
    )

@app.post("/invocations")
async def invoke_model(request: Request):
    """SageMaker inference endpoint"""
    try:
        request_data = await request.json()
        response = generate_response(request_data)
        return JSONResponse(content=response)
    except HTTPException as e:
        raise e
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": {"message": str(e), "type": "internal_server_error"}}
        )

@app.post("/v1/audio/transcriptions")
async def transcribe_audio_endpoint(request: Request):
    """Direct transcription endpoint compatible with OpenAI API format"""
    try:
        request_data = await request.json()
        audio_source = request_data.get("audio")
        language = request_data.get("language", "en")
        temperature = request_data.get("temperature", 0.0)

        if not audio_source:
            raise HTTPException(status_code=400, detail="Audio source required")

        result = transcribe_audio(audio_source, language, temperature)
        return JSONResponse(content={"text": result["text"]})

    except HTTPException as e:
        raise e
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": {"message": str(e), "type": "transcription_error"}}
        )

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    shutdown_vllm_server()
    sys.exit(0)

def main():
    """Main entry point"""
    os.environ.setdefault("PYTHONUNBUFFERED", "TRUE")

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    port = int(os.environ.get("SAGEMAKER_BIND_TO_PORT", "8080"))
    host = os.environ.get("SAGEMAKER_BIND_TO_HOST", "0.0.0.0")

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="warning",
        access_log=False,
        timeout_keep_alive=60,
        timeout_graceful_shutdown=30
    )

if __name__ == "__main__":
    main()