# Mistral AI Workshop: Open Models in Action 

Welcome to the Mistral AI Workshop! This hands-on workshop will guide you through deploying and using Mistral's powerful AI models on AWS, building real-world applications with vision and text capabilities, and fine-tuning Mistral models with custom datasets.

## 📚 Workshop Overview

This workshop consists of three comprehensive notebooks:

1. **Workshop 1: Mistral Model Deployment on AWS** - Use Pixtral Large from Bedrock, deploy Mistral Small 3 model from Bedrock Marketplace and Mistral OCR model from AWS Marketplace. 
2. **Workshop 2: MCP application with Mistral Workshop** - Build AI assistants with Model Context Protocol (MCP) and Mistral model on Bedrock.  
3. **Workshop 3: Mistral Small 3 Fine-tuning** - Customize models for domain-specific tasks with QLoRA 

## 🛠️ Prerequisites

### Required Setup (Complete Before Workshop)

#### 1. AWS Account Setup
- **Region**: Ensure you're working in **us-west-2** region
- **CloudFormation**: Deploy the `sagemaker-studio-template.yaml` successfully in your AWS account
- **Account Whitelisting**: Provide your AWS Account ID to workshop organizers for Mistral OCR model access. If your account is under an Organizational Unit (OU), provide the management account ID as well.

#### 2. Service Quota Increases
Request the following quota increases in **us-west-2** region:

| Service | Instance Type | Quota Type | Required Limit | Purpose |
|---------|---------------|------------|----------------|---------|
| SageMaker | `ml.g6.4xlarge` | Endpoint Usage | At least 1 | Host Mistral OCR model |
| SageMaker | `ml.g6.12xlarge` | Endpoint Usage | At least 1 | Host Mistral Small 3.0 model |
| SageMaker | `ml.g5.8xlarge` | Studio JupyterLab Apps | At least 1 | Run workshop notebooks |

📝 **How to request quota increases:**
1. Go to AWS Service Quotas console
2. Search for "Amazon SageMaker"
3. Find the specific quota (e.g., "ml.g6.4xlarge for endpoint usage")
4. Click "Request quota increase"
5. Set the new quota value and submit

#### 3. Amazon Bedrock Model Access
Enable access to the following models in Amazon Bedrock:
- **Pixtral Large**: `us.mistral.pixtral-large-2502-v1:0`

📝 **How to enable model access:**
1. Go to Amazon Bedrock console in us-west-2
2. Navigate to "Model access" in the left sidebar
3. Click "Request model access" 
4. Select "Mistral" models and request access to Pixtral Large

#### 4. API Keys and Tokens
Obtain the following credentials for the workshop:
- Google Maps API Key (Required for Workshop 2)
- Hugging Face Token (Required for Workshop 3)



## 🚀 Getting Started

### Step 1: Launch SageMaker Studio
1. Open AWS Console in **us-west-2** region
2. Navigate to Amazon SageMaker
3. Click "Studio" in the left sidebar
4. Launch SageMaker Studio

### Step 2: Clone Workshop Materials
```bash
git clone https://github.com/aws-samples/mistral-on-aws.git
cd Workshops/Open_Models_In_Action_EU_Roadshow
```

### Step 3: Install Dependencies
Run this in your SageMaker Studio terminal:
```bash
pip install -r requirements.txt
```

### Step 4: Start with Workshop 1
Open `1. Mistral_model_deployment_AWS.ipynb` and follow the instructions.

## 📋 Workshop Structure

### Workshop 1: Model Deployment 
- **Focus**: Deploy and use Mistral models on AWS
- **Models**: Pixtral Large (Bedrock), Mistral Small 3 (SageMaker), Mistral OCR (AWS Marketplace)
- **Use Cases**: Vision analysis, text classification, fraud detection, document understanding
- **Prerequisites**: Bedrock model access, SageMaker quotas

### Workshop 2: MCP Applications 
- **Focus**: Build AI assistants with MCP servers and external tools
- **Technology**: Model Context Protocol, Gradio web interface
- **Features**: time, maps integration, AWS documentation


### Workshop 3: Model Fine-tuning
- **Focus**: Fine-tune Mistral Small 3 for medical diagnosis
- **Technology**: QLoRA, Custom Model Import to Bedrock
- **Dataset**: Medical text data BI55/MedText: https://huggingface.co/datasets/BI55/MedText


## ⚠️ Important Notes

### Cost Management

**At the end of the workshop, please follow steps in the cleanup.ipynb file to delete all resources and the CloudFormation stack.** 

---

**Ready to get started?** Open `1. Mistral_model_deployment_AWS.ipynb` and begin your journey with Mistral AI on AWS! 🚀
