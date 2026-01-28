# Mistral Models on Amazon Bedrock - Examples

Sample notebooks demonstrating Mistral AI models on Amazon Bedrock.

## Notebooks

| Notebook | Description |
|----------|-------------|
| `mistral_bedrock_converse_api_tests.ipynb` | Using the **Converse API** |
| `mistral_bedrock_invoke_model_tests.ipynb` | Using the **invoke_model API** |

## Models Covered

- **Mistral Large 3** - Flagship multimodal model (text, vision, tool use)
- **Ministral 3B/8B/14B** - Efficient models for various tasks
- **Voxtral Mini/Small** - Audio transcription models
- **Magistral Small 1.2** - Advanced reasoning with vision

## Capabilities Demonstrated

- Text generation and multi-turn conversations
- Vision (image understanding)
- Tool use / function calling
- Audio transcription (Voxtral)
- Reasoning with [THINK] tokens (Magistral)

## Requirements

```bash
pip install boto3 pydub soundfile
```

For audio processing, FFmpeg is also required:
```bash
sudo apt install ffmpeg -y
```
