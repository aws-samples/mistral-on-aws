# Custom vLLM Container for Voxtral Model Deployment on SageMaker
# =============================================================
# Using official vLLM image as base to avoid compilation issues
# and ensure compatibility with CUDA and vLLM 0.10+

FROM --platform=linux/amd64 vllm/vllm-openai:v0.10.1.1

# Set environment variables for SageMaker
ENV MODEL_CACHE_DIR=/opt/ml/model
ENV TRANSFORMERS_CACHE=/tmp/transformers_cache
ENV HF_HOME=/tmp/hf_home
ENV VLLM_WORKER_MULTIPROC_METHOD=spawn

# Install system dependencies for audio processing
RUN apt-get update && apt-get install -y \
    libsndfile1 \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install audio dependencies required by both model.py and vLLM's internal audio pipeline
# - vllm[audio]: installs librosa + soundfile needed by vllm/multimodal/audio.py
# - mistral_common[audio]: needed by model.py for Voxtral audio preprocessing
# IMPORTANT: Do NOT install sagemaker, boto3, or other heavy packages here —
# they can upgrade torch and break the vLLM base image's torch/torchvision compatibility
RUN pip install --no-cache-dir \
    librosa>=0.10.2 \
    soundfile>=0.12.1 \
    "mistral_common[audio]>=1.8.1" \
    resampy>=0.4.3

# Create necessary directories
RUN mkdir -p /opt/ml/model /opt/ml/code /tmp/transformers_cache /tmp/hf_home

    
# Switch to non-root user
USER root

# Set working directory
WORKDIR /opt/ml/code

# Note: model.py, serving.properties, and requirements.txt will be provided via model_data

# Health check - disabled during startup to prevent container startup failures
HEALTHCHECK --interval=30s --timeout=30s --start-period=180s --retries=3 \
    CMD curl -f http://localhost:8080/ping || exit 1

# Expose the port for SageMaker
EXPOSE 8080

# Create serve script for SageMaker BYOC compatibility
RUN printf '#!/bin/bash\nif [ "$1" = "serve" ]; then\n    echo "🚀 Starting Voxtral BYOC container..."\n    echo "📁 Checking for files in /opt/ml/model/"\n    ls -la /opt/ml/model/ || echo "Cannot list /opt/ml/model/"\n    \n    # Install additional requirements if provided\n    if [ -f /opt/ml/model/requirements.txt ]; then\n        echo "📦 Installing additional requirements from /opt/ml/model/requirements.txt..."\n        pip install --root-user-action=ignore --no-deps -r /opt/ml/model/requirements.txt\n    else\n        echo "⚠️  No requirements.txt found in /opt/ml/model/"\n    fi\n    \n    # Copy model files to code directory for execution\n    if [ -f /opt/ml/model/model.py ]; then\n        echo "📄 Copying model.py from /opt/ml/model/ to /opt/ml/code/"\n        cp /opt/ml/model/model.py /opt/ml/code/\n        chmod +x /opt/ml/code/model.py\n    else\n        echo "❌ ERROR: model.py not found in /opt/ml/model/"\n        echo "📁 Available files in /opt/ml/model/:"\n        ls -la /opt/ml/model/ || echo "Cannot list directory"\n        exit 1\n    fi\n    \n    if [ -f /opt/ml/model/serving.properties ]; then\n        echo "⚙️  Copying serving.properties from /opt/ml/model/ to /opt/ml/code/"\n        cp /opt/ml/model/serving.properties /opt/ml/code/\n    else\n        echo "⚠️  WARNING: serving.properties not found in /opt/ml/model/"\n    fi\n    \n    echo "✅ File setup complete. Starting model server..."\n    # Start the model server\n    exec python3 /opt/ml/code/model.py\nelse\n    exec "$@"\nfi\n' > /usr/local/bin/serve && \
    chmod +x /usr/local/bin/serve

# Set the entrypoint for SageMaker BYOC
ENTRYPOINT ["/usr/local/bin/serve"]
CMD ["serve"]