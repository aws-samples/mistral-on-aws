#!/bin/bash

# Build and Push Custom vLLM Container to Amazon ECR
# ==================================================
# This script builds the custom vLLM container with latest version
# and pushes it to Amazon ECR for SageMaker deployment

set -e

# Configuration
AWS_REGION=${AWS_DEFAULT_REGION:-us-west-2}
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REPOSITORY_NAME="voxtral-vllm-byoc"
IMAGE_TAG="latest"
IMAGE_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${REPOSITORY_NAME}:${IMAGE_TAG}"

echo "🐳 Building and pushing custom vLLM container for Voxtral model"
echo "⚠️  IMPORTANT: Using vLLM >= 0.10.0 as required by Voxtral"
echo "Repository: ${REPOSITORY_NAME}"
echo "Image URI: ${IMAGE_URI}"
echo "Region: ${AWS_REGION}"

# Step 1: Create ECR repository if it doesn't exist
echo "📦 Creating ECR repository if it doesn't exist..."
aws ecr describe-repositories --repository-names ${REPOSITORY_NAME} --region ${AWS_REGION} 2>/dev/null || \
aws ecr create-repository --repository-name ${REPOSITORY_NAME} --region ${AWS_REGION}

# Step 2: Get ECR login token
echo "🔐 Logging into Amazon ECR..."
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

# Step 3: Build the Docker image
echo "🔨 Building Docker image..."
docker build -t ${REPOSITORY_NAME}:${IMAGE_TAG} .

# Step 4: Tag the image for ECR
echo "🏷️  Tagging image for ECR..."
docker tag ${REPOSITORY_NAME}:${IMAGE_TAG} ${IMAGE_URI}

# Step 5: Push the image to ECR
echo "⬆️  Pushing image to ECR..."
docker push ${IMAGE_URI}

echo "✅ Successfully built and pushed custom vLLM container!"
echo "Image URI: ${IMAGE_URI}"
echo ""
echo "You can now use this image URI in your SageMaker deployment:"
echo "image_uri = \"${IMAGE_URI}\""

# Optional: Clean up local images to save space
read -p "🗑️  Clean up local Docker images? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🧹 Cleaning up local images..."
    docker rmi ${REPOSITORY_NAME}:${IMAGE_TAG} ${IMAGE_URI}
    echo "Local images cleaned up"
fi

echo "🎉 Build and push completed successfully!"