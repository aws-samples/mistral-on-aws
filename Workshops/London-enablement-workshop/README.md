# Mistral on AWS Enablement Workshop 
This workshop contains a set of notebooks to show you how to use Mistral models in AWS environments, including Amazon Bedrock and Amazon Bedrock Marketplace. At the end, you will also learn how to build an agentic RAG application using Mistral model and LlamaIndex. 


## Prerequisites 
- An AWS account with access to Amazon Bedrock
- Access to Mistral Large 2 (mistral.mistral-large-2407-v1:0) in us-west-2
- **Increase ml.g6.12xlarge for endpoint usage to at least 2 in Amazon SageMaker service quota webpage in us-west-2**
- Basic understanding of Python and Jupyter notebooks

## Setup Instructions
1. Create an Amazon SageMaker domain in region **us-west-2**. This step may take a few minutes. 
2. Create a SageMaker domain user profile. 
3. Launch SageMaker Studio, select JupyterLab, and create a space. 
4. Select the instance ml.t3.medium and the image SageMaker Distribution 2.3.1, then run the space.
5. Navigate to the AWS Bedrock service in the AWS console. On the left banner, select “Model access.” 
6. Click on “Modify model access.” 
7. Select the models: Mistral Large 2 (24.07) and Titan Text Embeddings V2 from the list, and request access to these models. 
8. Go to the SageMaker user profile details and find the execution role that the SageMaker notebook uses. It should look similar to: 
AmazonSageMaker-ExecutionRole-20250213T123456
9. Go to AWS console IAM service, add “AmazonBedrockFullAccess” to the execution role. 
10. Clone the workshop repository in the SageMaker JupyterLab terminal:
```bash
   git clone https://github.com/aws-samples/mistral-on-aws.git
   cd notebooks/London-enablement-workshop
```
11. Install the required Python packages by running the following command in the terminal:
```bash
   pip install -r requirements.txt -q
```


## Workshop Content

### Notebook1: 
- Mistral model prompt capabilities and best practices 

### Notebook2: 
- Oveview of Mistral Small 3 model 
- Deploying Mistral Small 3 model in Amazon Bedrock Marketplace
- Examples of use cases, such as fraud detection and sentiment analysis

### Notebook3: 
- Overview of Mistral Pixtral 12B model, Vision Language Model (VLM)
- Deploying Pixtral 12B model in Amazon Bedrock Marketplace
- Examples of use cases, such as visual logic reasoning and vehicle damage assessment

### Notebook4: 
- Overall agentic RAG application architecture
- Integrating API tools into the application 
- Building RAG with Amazon OpenSearch Serverless and integrating into the application
- Testing the final chatbot




