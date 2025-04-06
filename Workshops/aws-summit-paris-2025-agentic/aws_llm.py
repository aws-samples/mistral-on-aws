import boto3
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Self
from tools_utils import tool_map
from utils import load_image_file_to_bytes, get_file_extension

AWS_BEDROCK_MISTRAL_LARGE_MODEL_ID = "mistral.mistral-large-2407-v1:0"
AWS_SAGEMAKER_PIXTRAL_12B_ENDPOINT_ARN = (
    "arn:aws:sagemaker:us-west-2:777356365391:endpoint/harizo-tests-pixtral12b"
)
AWS_REGION = "us-west-2"
AWS_BEDROCK_DEFAULT_INFERENCE_CONFIG = {"temperature": 0.0, "maxTokens": 4096}
AWS_BEDROCK_DEFAULT_SYSTEM_MESSAGE = """
Tu es un assistant serviable et informel. Ton role est de guider l'utilisateur
dans sa découverte de la ville de Paris. Réponds toujours aux questions en Français.
"""


client = boto3.client(service_name="bedrock-runtime", region_name=AWS_REGION)

with Path("tools_demo.json").open(mode="r") as f_in:
    tools_demo = json.load(f_in)


class Agent:
    def __init__(self):
        self.model_id = AWS_BEDROCK_MISTRAL_LARGE_MODEL_ID
        self.messages: List[Dict[str, Any]] = []
        self.tools: Optional[Dict[str, Any]] = None
        self.system_message_content = AWS_BEDROCK_DEFAULT_SYSTEM_MESSAGE

    def show_messages(self):
        print(json.dumps(self.messages, indent=4))

    def save_messages(self, file_name: str):
        with Path(file_name).open(mode="w") as f_in:
            json.dump(self.messages, f_in)

    def ask(
        self, user_message_content: str, image_paths: Optional[List[str]] = None
    ) -> Self:
        user_message = {"role": "user", "content": [{"text": user_message_content}]}
        converse_params = {
            "modelId": self.model_id,
            "messages": self.messages,
            "inferenceConfig": AWS_BEDROCK_DEFAULT_INFERENCE_CONFIG,
            "system": [{"text": self.system_message_content}],
        }
        if image_paths:
            # Override default model id to force multimodal usage
            converse_params["modelId"] = AWS_SAGEMAKER_PIXTRAL_12B_ENDPOINT_ARN
            for imgp in image_paths:
                user_message["content"].append(
                    {
                        "image": {
                            "format": get_file_extension(imgp),
                            "source": {"bytes": load_image_file_to_bytes(imgp)},
                        }
                    }
                )
        if self.tools:
            converse_params.update({"toolConfig": self.tools})
        self.messages.append(user_message)
        try:
            resp = client.converse(**converse_params)
            output_message = resp["output"]["message"]
            self.messages.append(output_message)
            if tool_use := output_message["content"][0].get("toolUse", None):
                tool_use_id = tool_use["toolUseId"]
                func_name = tool_use["name"]
                func_args = tool_use["input"]
                func = tool_map[func_name]
                func_out = func(**func_args)
                tool_message_content = {
                    "toolResult": {
                        "toolUseId": tool_use_id,
                        "content": [{"json": func_out}],
                    }
                }
                tool_message = {"role": "user", "content": [tool_message_content]}
                self.messages.append(tool_message)
                try:
                    resp_tool_use = client.converse(**converse_params)
                    self.messages.append(resp_tool_use["output"]["message"])
                except Exception as e:
                    print(f"Error during tool use: {e}")
            print(self.messages[-1]["content"][0]["text"])
        except Exception as e:
            print(f"Conversation error: {e}")
            raise
