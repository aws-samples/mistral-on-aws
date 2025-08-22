# Mistral Voxtral vLLM BYOC Deployment on SageMaker Guide

This guide explains how to deploy Mistral AI's Voxtral models (Voxtral-Mini-3B-2507 and Voxtral-Small-24B-2507) using a custom vLLM container (BYOC - Bring Your Own Container) on Amazon SageMaker.

## Overview

The BYOC approach provides several advantages over using pre-built containers:
- **Required vLLM version** (v0.10.0+) - Official Voxtral requirement
- **Full control** over the inference environment and dependencies
- **Custom optimizations** specifically tailored for Voxtral models
- **Future-proof** deployment that can be easily updated
- **Multi-model support** - Both Mini and Small models supported with this solution

## Supported Models

| Model | Size | Instance Type | Tensor Parallel | Use Cases |
|-------|------|---------------|-----------------|-----------|
| **Voxtral-Mini-3B-2507** | 3B | ml.g6.4xlarge | 1 | Audio transcription and understanding, basic chat |
| **Voxtral-Small-24B-2507** | 24B | ml.g6.12xlarge | 4 | Advanced chat, function calling, audio transcription and understanding |

## Files Structure

### Core BYOC Files
- **`Dockerfile`** - Custom container definition with vLLM v0.10.0+ (required for Voxtral)
- **`code/model.py`** - Custom inference handler with OpenAI-compatible API
- **`code/serving.properties`** - Voxtral server configurations (modify for different models)
- **`code/requirements.txt`** - Additional Python dependencies including mistral_common
- **`build_and_push.sh`** - Script to build and push container to ECR

### Notebook and Test Files
- **`Voxtral-vLLM-BYOC-SageMaker.ipynb`** - Complete BYOC deployment notebook

## Quick Start

### Prerequisites

**Software Requirements:**
- vLLM >= 0.10.0 (critical requirement)
- mistral_common >= 1.8.1

**AWS Account Requirements:**
- This solution is tested in SageMaker notebooks with **m5.4xlarge instance** and **100GB storage**
- **ECR permissions**: Add policy `EC2InstanceProfileForImageBuilderECRContainerBuilds` to SageMaker execution role
- **S3 permissions**: Required for model artifact storage
- **Sufficient quotas**: 
  - `ml.g6.4xlarge` SageMaker endpoint for Voxtral Mini
  - `ml.g6.12xlarge` SageMaker endpoint for Voxtral Small

### 1. Build and Push Custom Container

```bash
# Make the script executable
chmod +x build_and_push.sh

# Build and push to ECR (includes vLLM v0.10.0+)
./build_and_push.sh
```

**Note**: Container building takes approximately **10 minutes**.

### 2. Configure Model Settings

Before deployment, modify the configuration in `code/serving.properties`:

#### For Voxtral Mini (3B model):
```properties
option.model_id=mistralai/Voxtral-Mini-3B-2507
option.tensor_parallel_degree=1
```
**Instance**: Use `ml.g6.4xlarge` in the notebook

#### For Voxtral Small (24B model):
```properties
option.model_id=mistralai/Voxtral-Small-24B-2507
option.tensor_parallel_degree=4
```
**Instance**: Use `ml.g6.12xlarge` in the notebook (enables multi-GPU utilization)

### 3. Deploy Using Jupyter Notebook

1. Open the notebook: `Voxtral-vLLM-BYOC-SageMaker.ipynb`
2. Follow the step-by-step instructions to deploy the model
3. The notebook will:
   - Configure SageMaker model with your custom container
   - Upload model code to S3
   - Deploy real-time inference endpoint
   - Test with various input types (text, audio, function calling)

## Key Features

### Flexible BYOC Architecture
- **Container Image**: Base dependencies, vLLM, system packages (build once)
- **Model Code**: Configuration files provided via S3 (update as needed)

### Multimodal Processing
- **Text**: Standard chat completion format
- **Audio**: Base64 encoded or URL-based audio input  
- **Mixed**: Combined text and audio in single request

### Function Calling (Voxtral-Small only)


## Updating the Solution

### Update Model Configuration
1. Modify files in `code/` directory
2. Re-run deployment notebook (no Docker rebuild needed)
3. Container will download and use updated configuration

### Update vLLM Version
1. Update version in `Dockerfile`
2. Run `./build_and_push.sh` to rebuild container
3. Re-deploy with new image
