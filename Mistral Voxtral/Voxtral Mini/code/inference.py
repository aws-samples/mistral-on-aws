import json
import logging
import os
import torch
from transformers import VoxtralForConditionalGeneration, AutoProcessor
import librosa
import numpy as np
import base64
import io
import requests
from urllib.parse import urlparse

# Suppress all logging to prevent base64 from appearing in logs
logging.getLogger().setLevel(logging.ERROR)
logging.getLogger('transformers').setLevel(logging.ERROR)
logging.getLogger('torch').setLevel(logging.ERROR)
logging.getLogger('librosa').setLevel(logging.ERROR)

# Disable all loggers that might print request data
for logger_name in ['sagemaker', 'mms', 'werkzeug', 'urllib3', 'requests']:
    logging.getLogger(logger_name).setLevel(logging.ERROR)

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)  # Only show errors

class VoxtralHandler:
    def __init__(self):
        self.model = None
        self.processor = None
        self.device = None
        
    def initialize(self, context,model_dir=None):
        """Initialize the model for inference"""
        logger.info("Initializing Voxtral model")
        
        # Get model path from environment or context

        model_path = model_dir
        logger.info(f"Using model from local directory: {model_path}")
        
        # Set device
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Using device: {self.device}")
        
        try:
            # Load processor and model with trust_remote_code
            self.processor = AutoProcessor.from_pretrained(
                model_path,
                trust_remote_code=True
            )
            
            # Use VoxtralForConditionalGeneration instead of AutoModelForSpeechSeq2Seq
            self.model = VoxtralForConditionalGeneration.from_pretrained(
                model_path,
                torch_dtype=torch.bfloat16,
                device_map=self.device,
                trust_remote_code=True
            )
            
            self.model.eval()
            
            logger.info("Model loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load model: {str(e)}")
            raise e
    
    def _load_audio_from_url(self, url):
        """Load audio from URL"""
        try:
            response = requests.get(url)
            response.raise_for_status()
            audio_data = io.BytesIO(response.content)
            audio_array, _ = librosa.load(audio_data, sr=16000)
            return audio_array
        except Exception as e:
            logger.error(f"Failed to load audio from URL {url}: {str(e)}")
            raise e
    
    def _load_audio_from_base64(self, audio_b64):
        """Load audio from base64 string"""
        try:
            audio_bytes = base64.b64decode(audio_b64)
            audio_data = io.BytesIO(audio_bytes)
            audio_array, _ = librosa.load(audio_data, sr=16000)
            return audio_array
        except Exception as e:
            logger.error(f"Failed to load audio from base64: {str(e)}")
            raise e
    
    def _save_base64_as_temp_file(self, audio_b64):
        """Save base64 audio as temporary file and return file path"""
        try:
            import tempfile
            import gc
            
            # Decode base64 to bytes with memory optimization
            audio_bytes = base64.b64decode(audio_b64)
            
            # Clear the base64 string from memory
            del audio_b64
            gc.collect()
            
            # Create temporary file with appropriate extension
            temp_file = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
            temp_file.write(audio_bytes)
            temp_file.flush()
            temp_file.close()
            
            # Clear audio bytes from memory
            del audio_bytes
            gc.collect()
            
            # Store temp file for cleanup
            if not hasattr(self, '_temp_files'):
                self._temp_files = []
            self._temp_files.append(temp_file.name)
            
            return temp_file.name
            
        except Exception as e:
            raise ValueError(f"Failed to process audio data: {str(e)[:100]}")  # Truncate error message
    
    def _cleanup_temp_files(self):
        """Clean up temporary files"""
        if hasattr(self, '_temp_files'):
            import os
            for temp_file in self._temp_files:
                try:
                    os.unlink(temp_file)
                except:
                    pass  # Ignore cleanup errors
            self._temp_files = []
    
    
    def preprocess(self, data):
        """Preprocess the input data to match Voxtral's conversation format"""
        try:
            if isinstance(data, list):
                data = data[0]
            
            # Process without logging to avoid any data leakage
            
            # Handle different input formats
            if isinstance(data, dict):
                if 'body' in data:
                    body = data['body']
                    if isinstance(body, bytes):
                        body = body.decode('utf-8')
                    if isinstance(body, str):
                        body = json.loads(body)
                    data = body
                
                # Build conversation format
                conversation = [{"role": "user", "content": []}]
                
                # Handle conversation input (preferred format)
                if 'conversation' in data:
                    conversation = data['conversation']
                    # Normalize conversation format - ensure all content is properly structured
                    normalized_conversation = []
                    for message in conversation:
                        normalized_message = {"role": message["role"], "content": []}
                        
                        # Handle both list and string content
                        if isinstance(message["content"], str):
                            # Convert string content to structured format
                            normalized_message["content"] = [{"type": "text", "text": message["content"]}]
                        elif isinstance(message["content"], list):
                            # Ensure each content item is properly structured
                            normalized_content = []
                            for content_item in message["content"]:
                                if isinstance(content_item, dict):
                                    normalized_content.append(content_item)
                                elif isinstance(content_item, str):
                                    normalized_content.append({"type": "text", "text": content_item})
                                else:
                                    normalized_content.append(content_item)
                            normalized_message["content"] = normalized_content
                        else:
                            normalized_message["content"] = []
                        
                        normalized_conversation.append(normalized_message)
                    
                    conversation = normalized_conversation
                else:
                    # Handle individual inputs and build conversation
                    content = []
                    
                    # Handle audio inputs
                    if 'audio' in data:
                        audio_items = data['audio'] if isinstance(data['audio'], list) else [data['audio']]
                        for audio_item in audio_items:
                            if isinstance(audio_item, str):
                                # Check if it's a URL
                                parsed = urlparse(audio_item)
                                if parsed.scheme in ['http', 'https']:
                                    content.append({"type": "audio", "path": audio_item})
                                else:
                                    # Assume base64
                                    content.append({"type": "audio", "data": audio_item})
                            elif isinstance(audio_item, dict):
                                content.append(audio_item)
                    
                    # Handle text input
                    if 'text' in data:
                        content.append({"type": "text", "text": data['text']})
                    elif 'prompt' in data:
                        content.append({"type": "text", "text": data['prompt']})
                    
                    # If only audio and no text, it's audio-only scenario
                    if content and not any(item.get('type') == 'text' for item in content):
                        # Audio-only case - no need to add text
                        pass
                    
                    conversation[0]['content'] = content
                
                # Get generation parameters
                params = {
                    'max_new_tokens': data.get('max_new_tokens', 500),
                    'temperature': data.get('temperature', 1.0),
                    'transcribe_only': data.get('transcribe_only', False),
                    'language': data.get('language', 'en')
                }
                
                return conversation, params
                
        except Exception as e:
            logger.error(f"Error in preprocessing: {str(e)}")
            raise e
    
    def inference(self, processed_data):
        """Run inference using Voxtral's chat template approach or transcription-only"""
        try:
            conversation, params = processed_data
            
            # Check if transcribe_only mode is requested
            if params.get('transcribe_only', False):
                return self._transcribe_only(conversation, params)
            
            # Process conversation with audio loading
            processed_conversation = []
            for message in conversation:
                processed_message = {"role": message["role"], "content": []}
                
                # Handle both list and string content
                if isinstance(message["content"], str):
                    # Convert string content to structured format
                    content_items = [{"type": "text", "text": message["content"]}]
                elif isinstance(message["content"], list):
                    content_items = message["content"]
                else:
                    content_items = []
                
                for content_item in content_items:
                    # Handle both dict and string content items
                    if isinstance(content_item, dict):
                        if content_item.get("type") == "audio":
                            if "path" in content_item:
                                # Load from URL
                                processed_message["content"].append({
                                    "type": "audio",
                                    "path": content_item["path"]
                                })
                            elif "data" in content_item:
                                # Load from base64 and save as temporary file
                                temp_file_path = self._save_base64_as_temp_file(content_item["data"])
                                processed_message["content"].append({
                                    "type": "audio", 
                                    "path": temp_file_path
                                })
                        else:
                            processed_message["content"].append(content_item)
                    elif isinstance(content_item, str):
                        # Handle string content (like assistant responses)
                        processed_message["content"].append({
                            "type": "text",
                            "text": content_item
                        })
                    else:
                        # Pass through other types as-is
                        processed_message["content"].append(content_item)
                
                processed_conversation.append(processed_message)
            
            # Apply chat template
            inputs = self.processor.apply_chat_template(processed_conversation)
            inputs = inputs.to(self.device, dtype=torch.bfloat16)
            
            # Generate response
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=params['max_new_tokens'],
                    temperature=params.get('temperature')
                )
            
            # Decode only the generated part (exclude input)
            decoded_outputs = self.processor.batch_decode(
                outputs[:, inputs.input_ids.shape[1]:], 
                skip_special_tokens=True
            )
            
            # Clean up temporary files
            self._cleanup_temp_files()
            
            return decoded_outputs[0]
            
        except Exception as e:
            # Clean up temp files on error
            self._cleanup_temp_files()
            raise e
    
    def _transcribe_only(self, conversation, params):
        """Handle transcription-only requests using apply_transcription_request"""
        try:
            # Extract audio from conversation
            audio_path = None
            audio_type = None
            for message in conversation:
                for content_item in message["content"]:
                    if content_item["type"] == "audio":
                        if "path" in content_item:
                            audio_path = content_item["path"]
                            break
                        elif "data" in content_item:
                            # For base64 data, save as temporary file
                            audio_path = self._save_base64_as_temp_file(content_item["data"])
                            audio_type = 'base64'
                            break
                if audio_path:
                    break
            
            if not audio_path:
                raise ValueError("No audio found in conversation for transcription")
            
            # Use apply_transcription_request for transcription-only
            language = params.get('language', 'en')
            
            # Get model_id - this should be the repo_id used for the model
            # We'll try to get it from the processor config or use a default
            model_id = getattr(self.processor, 'name_or_path', 'mistralai/Voxtral-Mini-3B-2507')
            
            inputs = self.processor.apply_transcription_request(
                language=language, 
                audio=audio_path, 
                model_id=model_id
            )
            inputs = inputs.to(self.device, dtype=torch.bfloat16)
            
            # Generate transcription
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs, 
                    max_new_tokens=params.get('max_new_tokens', 500)
                )
            
            # Decode only the generated part (exclude input)
            decoded_outputs = self.processor.batch_decode(
                outputs[:, inputs.input_ids.shape[1]:], 
                skip_special_tokens=True
            )
            
            # Clean up temporary files
            self._cleanup_temp_files()
            
            return decoded_outputs[0]
            
        except Exception as e:
            # Clean up temp files on error
            self._cleanup_temp_files()
            raise e
    
    def postprocess(self, inference_output):
        """Postprocess the inference output"""
        return {
            "response": inference_output,
            "status": "success"
        }

# Global handler instance
_handler = VoxtralHandler()

def model_fn(model_dir):
    """Load the model for inference"""
    _handler.initialize(None, model_dir)  # Pass model_dir
    return _handler

def input_fn(request_body, request_content_type):
    """Parse input data for inference"""
    if request_content_type == "application/json":
        # Check payload size to prevent memory issues
        if len(request_body) > 30 * 1024 * 1024:  # 30MB limit (reduced)
            raise ValueError("Payload too large (>30MB)")
        
        # Parse JSON with minimal memory footprint
        try:
            input_data = json.loads(request_body)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {str(e)}")
        
        # Clear request_body from memory immediately
        del request_body
        
    else:
        raise ValueError(f"Unsupported content type: {request_content_type}")
    
    return _handler.preprocess(input_data)

def predict_fn(input_data, model):
    """Run prediction"""
    return model.inference(input_data)

def output_fn(prediction, response_content_type):
    """Format the output"""
    result = _handler.postprocess(prediction)
    
    if response_content_type == "application/json":
        return json.dumps(result)
    else:
        raise ValueError(f"Unsupported response content type: {response_content_type}")