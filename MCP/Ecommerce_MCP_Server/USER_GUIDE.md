# E-Commerce MCP Server - Deployment & User Guide

A comprehensive guide for deploying the E-Commerce MCP (Model Context Protocol) Server on AWS and connecting it to MCP clients like Mistral AI Studio, Claude Desktop, and custom agents.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [Deployment Guide](#deployment-guide)
   - [Step 1: Clone and Prepare](#step-1-clone-and-prepare)
   - [Step 2: Deploy Infrastructure with CDK](#step-2-deploy-infrastructure-with-cdk)
   - [Step 3: Build and Push Docker Image](#step-3-build-and-push-docker-image)
   - [Step 4: Deploy to ECS Fargate](#step-4-deploy-to-ecs-fargate)
   - [Step 5: Verify Deployment](#step-5-verify-deployment)
5. [MCP Client Configuration](#mcp-client-configuration)
   - [Mistral AI Studio](#mistral-ai-studio)
   - [Claude Desktop](#claude-desktop)
   - [Custom Python Agents](#custom-python-agents)
6. [API Reference](#api-reference)
7. [Troubleshooting](#troubleshooting)
8. [Cost Estimation](#cost-estimation)

---

## Overview

The E-Commerce MCP Server provides AI agents with tools to interact with an e-commerce platform:

| Tool | Auth Required | Description |
|------|---------------|-------------|
| `search_products` | No | Search product catalog by query, category, price range |
| `order_product` | Yes | Place orders for products |
| `write_product_review` | Yes | Submit product reviews with ratings |
| `get_order_history` | Yes | View customer's order history |
| `initiate_return` | Yes | Start a return request for an order |

---

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   MCP Client    │────▶│   ECS Fargate   │────▶│    DynamoDB     │
│ (Mistral/       |     |                 |     |                 |
|  Strands Agents)│     │   (MCP Server)  │     │   (5 Tables)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌─────────────────┐
                        │  AWS Cognito    │
                        │ (Authentication)│
                        └─────────────────┘
```

**AWS Services Used:**
- **ECS Fargate** - Serverless container hosting
- **ECR** - Docker image registry
- **DynamoDB** - NoSQL database for products, orders, customers, reviews, returns
- **Cognito** - User authentication and OAuth2
- **CloudWatch** - Logging and monitoring

---

## Prerequisites

### Required Tools
- AWS CLI v2 configured with appropriate credentials
- Docker (for building images)
- Node.js 18+ and npm (for CDK)
- Python 3.10+ (for local testing)

### AWS Permissions
Your IAM user/role needs permissions for:
- ECS (clusters, services, task definitions)
- ECR (repositories, push/pull)
- DynamoDB (create tables, read/write)
- Cognito (user pools, app clients)
- IAM (create roles)
- CloudWatch Logs

### Verify Prerequisites
```bash
# Check AWS CLI
aws --version
aws sts get-caller-identity

# Check Docker
docker --version
docker info

# Check Node.js
node --version
npm --version

# Check Python
python3 --version
```

---

## Deployment Guide

### Step 1: Clone and Prepare

```bash
# Clone or download the project
cd /path/to/your/workspace

# Project structure
MCP-Mistral-2/
├── ecommerce-mcp-cdk/     # CDK infrastructure code
│   ├── lib/
│   ├── scripts/
│   └── package.json
├── mcp_server/            # MCP server application
│   ├── server.py
│   ├── Dockerfile
│   ├── deploy.sh
│   └── requirements.txt
└── USER_GUIDE.md          # This file
```

### Step 2: Deploy Infrastructure with CDK

The CDK stack deploys DynamoDB tables, Cognito user pool, and ECR repository.

```bash
cd ecommerce-mcp-cdk

# Install dependencies
npm install

# Bootstrap CDK (first time only)
npx cdk bootstrap

# Deploy infrastructure
npx cdk deploy --require-approval never

# Note the outputs:
# - UserPoolId
# - UserPoolClientId
# - ECR Repository URI
```

**CDK Outputs Example:**
```
EcommerceMcpCdkStack.UserPoolId = us-west-2_XXXXXXXX
EcommerceMcpCdkStack.UserPoolClientId = XXXXXXXXXXXXXXXXXX
EcommerceMcpCdkStack.ECRRepositoryUri = 123456789012.dkr.ecr.us-west-2.amazonaws.com/ecommerce-mcp-server
```

#### Load Demo Data

```bash
# Load sample products, customers, and orders
cd scripts
python3 load_demo_data.py

# Create demo users in Cognito
python3 create_demo_users.py
```

### Step 3: Build and Push Docker Image

```bash
cd ../mcp_server

# Option A: Use the deployment script (recommended)
chmod +x deploy.sh
./deploy.sh

# Option B: Manual build
docker build -t ecommerce-mcp-server .

# Get AWS account ID
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=us-west-2

# Tag image
docker tag ecommerce-mcp-server:latest \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/ecommerce-mcp-server:latest

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Push image
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/ecommerce-mcp-server:latest
```

### Step 4: Deploy to ECS Fargate

#### 4.1 Create IAM Roles

```bash
# Create trust policy
cat > /tmp/ecs-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create execution role
aws iam create-role \
  --role-name ecsTaskExecutionRole \
  --assume-role-policy-document file:///tmp/ecs-trust-policy.json

aws iam attach-role-policy \
  --role-name ecsTaskExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

# Create task role (for DynamoDB and Cognito access)
aws iam create-role \
  --role-name ecsTaskRole \
  --assume-role-policy-document file:///tmp/ecs-trust-policy.json

aws iam attach-role-policy \
  --role-name ecsTaskRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess

aws iam attach-role-policy \
  --role-name ecsTaskRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonCognitoPowerUser
```

#### 4.2 Create ECS Cluster

```bash
aws ecs create-cluster \
  --cluster-name ecommerce-mcp-cluster \
  --region us-west-2
```

#### 4.3 Create CloudWatch Log Group

```bash
aws logs create-log-group \
  --log-group-name /ecs/ecommerce-mcp-server \
  --region us-west-2
```

#### 4.4 Register Task Definition

```bash
# Set your values
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export COGNITO_USER_POOL_ID="us-west-2_XXXXXXXX"  # From CDK output
export COGNITO_CLIENT_ID="XXXXXXXXXXXXXXXXXX"     # From CDK output

# Create task definition
cat > /tmp/task-definition.json << EOF
{
  "family": "ecommerce-mcp-server",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "arn:aws:iam::${AWS_ACCOUNT_ID}:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::${AWS_ACCOUNT_ID}:role/ecsTaskRole",
  "containerDefinitions": [
    {
      "name": "ecommerce-mcp-server",
      "image": "${AWS_ACCOUNT_ID}.dkr.ecr.us-west-2.amazonaws.com/ecommerce-mcp-server:latest",
      "cpu": 256,
      "memory": 512,
      "essential": true,
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "AWS_REGION", "value": "us-west-2"},
        {"name": "COGNITO_USER_POOL_ID", "value": "${COGNITO_USER_POOL_ID}"},
        {"name": "COGNITO_CLIENT_ID", "value": "${COGNITO_CLIENT_ID}"},
        {"name": "PRODUCTS_TABLE", "value": "ecommerce-products"},
        {"name": "CUSTOMERS_TABLE", "value": "ecommerce-customers"},
        {"name": "ORDERS_TABLE", "value": "ecommerce-orders"},
        {"name": "REVIEWS_TABLE", "value": "ecommerce-reviews"},
        {"name": "RETURNS_TABLE", "value": "ecommerce-returns"},
        {"name": "PORT", "value": "8000"},
        {"name": "HOST", "value": "0.0.0.0"}
      ],
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      },
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/ecommerce-mcp-server",
          "awslogs-region": "us-west-2",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
EOF

aws ecs register-task-definition \
  --cli-input-json file:///tmp/task-definition.json \
  --region us-west-2
```

#### 4.5 Create Security Group

```bash
# Get default VPC
export VPC_ID=$(aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" \
  --query "Vpcs[0].VpcId" --output text --region us-west-2)

# Create security group
export SG_ID=$(aws ec2 create-security-group \
  --group-name ecommerce-mcp-sg \
  --description "Security group for E-Commerce MCP Server" \
  --vpc-id $VPC_ID \
  --query 'GroupId' \
  --output text \
  --region us-west-2)

# Allow port 8000 inbound
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp \
  --port 8000 \
  --cidr 0.0.0.0/0 \
  --region us-west-2

echo "Security Group ID: $SG_ID"
```

#### 4.6 Create ECS Service

```bash
# Get subnets
export SUBNET_1=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" \
  --query "Subnets[0].SubnetId" --output text --region us-west-2)
export SUBNET_2=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" \
  --query "Subnets[1].SubnetId" --output text --region us-west-2)

# Create service
aws ecs create-service \
  --cluster ecommerce-mcp-cluster \
  --service-name ecommerce-mcp-service \
  --task-definition ecommerce-mcp-server \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_1,$SUBNET_2],securityGroups=[$SG_ID],assignPublicIp=ENABLED}" \
  --region us-west-2
```

### Step 5: Verify Deployment

#### Get Public IP

```bash
# Wait for task to start (60-90 seconds)
sleep 90

# Get task ARN
TASK_ARN=$(aws ecs list-tasks \
  --cluster ecommerce-mcp-cluster \
  --service-name ecommerce-mcp-service \
  --query "taskArns[0]" \
  --output text \
  --region us-west-2)

# Get ENI ID
ENI_ID=$(aws ecs describe-tasks \
  --cluster ecommerce-mcp-cluster \
  --tasks "$TASK_ARN" \
  --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' \
  --output text \
  --region us-west-2)

# Get public IP
PUBLIC_IP=$(aws ec2 describe-network-interfaces \
  --network-interface-ids "$ENI_ID" \
  --query 'NetworkInterfaces[0].Association.PublicIp' \
  --output text \
  --region us-west-2)

echo "==================================="
echo "MCP Server Endpoint: http://$PUBLIC_IP:8000"
echo "==================================="
```

#### Test Endpoints

```bash
export ENDPOINT="http://$PUBLIC_IP:8000"

# 1. Health check
curl $ENDPOINT/health

# 2. Search products (public)
curl -X POST $ENDPOINT/tools/search_products \
  -H "Content-Type: application/json" \
  -d '{"query": "laptop", "max_price": 1500}'

# 3. Login to get token
curl -X POST $ENDPOINT/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "demo1@example.com", "password": "Demo123!"}'
```

---

## MCP Client Configuration

### Mistral AI Studio

#### Option 1: Direct HTTP Connection

1. Open **Mistral AI Studio** (https://studio.mistral.ai)
2. Go to **Settings** > **MCP Servers** > **Add New**
3. Configure:
   ```
   Name: E-Commerce Tools
   URL: http://<YOUR_PUBLIC_IP>:8000
   Authentication: Username/Password
   Email: demo1@example.com
   Password: Demo123!
   ```
4. Click **Save** and **Enable**

#### Option 2: Using Mistral Agent SDK

```python
from mistralai import Mistral
from mistralai.models import MCPServer

client = Mistral(api_key="your-api-key")

# Configure MCP server
mcp_server = MCPServer(
    url="http://<YOUR_PUBLIC_IP>:8000",
    auth={
        "type": "basic",
        "username": "demo1@example.com",
        "password": "Demo123!"
    }
)

# Create agent with MCP tools
response = client.agents.complete(
    agent_id="your-agent-id",
    messages=[{"role": "user", "content": "Search for laptops under $1000"}],
    mcp_servers=[mcp_server]
)
```

### Claude Desktop

Edit the Claude Desktop configuration file:

**macOS:** `~/.config/claude/config.json`
**Windows:** `%APPDATA%\Claude\config.json`
**Linux:** `~/.config/claude/config.json`

```json
{
  "mcpServers": {
    "ecommerce": {
      "url": "http://<YOUR_PUBLIC_IP>:8000",
      "auth": {
        "type": "oauth2",
        "flow": "authorization_code",
        "authorization_endpoint": "https://ecommerce-mcp-demo.auth.us-west-2.amazoncognito.com/oauth2/authorize",
        "token_endpoint": "https://ecommerce-mcp-demo.auth.us-west-2.amazoncognito.com/oauth2/token",
        "client_id": "<YOUR_COGNITO_CLIENT_ID>",
        "scopes": ["openid", "email", "profile"]
      }
    }
  }
}
```

**Restart Claude Desktop** after saving.

**Usage Example:**
```
You: Show me laptops under $1500
Claude: [Uses search_products tool]

You: Order the first one for me
Claude: [Uses order_product tool with authentication]
```

### Custom Python Agents

#### Using Strands Agent Framework

```python
import requests
from strands import Agent, MCPServer

class ECommerceAuth:
    def __init__(self, endpoint, email, password):
        self.endpoint = endpoint
        self.email = email
        self.password = password
        self.token = None

    def get_token(self):
        if self.token is None:
            response = requests.post(
                f"{self.endpoint}/auth/login",
                json={"email": self.email, "password": self.password}
            )
            self.token = response.json()["access_token"]
        return self.token

# Initialize auth
auth = ECommerceAuth(
    endpoint="http://<YOUR_PUBLIC_IP>:8000",
    email="demo1@example.com",
    password="Demo123!"
)

# Configure MCP server
ecommerce_mcp = MCPServer(
    url="http://<YOUR_PUBLIC_IP>:8000",
    auth_provider=auth.get_token,
    token_refresh_interval=3600  # Refresh every hour
)

# Create agent
agent = Agent(
    name="Shopping Assistant",
    mcp_servers=[ecommerce_mcp],
    system_prompt="You are a helpful shopping assistant."
)

# Use the agent
response = agent.chat("Find me a good laptop under $1500 and help me order it")
print(response)
```

#### Using Raw HTTP Requests

```python
import requests

ENDPOINT = "http://<YOUR_PUBLIC_IP>:8000"

# 1. Search products (no auth required)
def search_products(query, max_price=None, category=None):
    payload = {"query": query}
    if max_price:
        payload["max_price"] = max_price
    if category:
        payload["category"] = category

    response = requests.post(
        f"{ENDPOINT}/tools/search_products",
        json=payload
    )
    return response.json()

# 2. Login and get token
def login(email, password):
    response = requests.post(
        f"{ENDPOINT}/auth/login",
        json={"email": email, "password": password}
    )
    return response.json()["access_token"]

# 3. Order product (auth required)
def order_product(token, product_id, quantity=1):
    response = requests.post(
        f"{ENDPOINT}/tools/order_product",
        json={"product_id": product_id, "quantity": quantity},
        headers={"Authorization": f"Bearer {token}"}
    )
    return response.json()

# 4. Write review (auth required)
def write_review(token, product_id, rating, review_text):
    response = requests.post(
        f"{ENDPOINT}/tools/write_product_review",
        json={
            "product_id": product_id,
            "rating": rating,
            "review_text": review_text
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    return response.json()

# Example usage
if __name__ == "__main__":
    # Search (public)
    products = search_products("laptop", max_price=1500)
    print(f"Found {products['count']} products")

    # Login
    token = login("demo1@example.com", "Demo123!")
    print("Logged in successfully")

    # Order
    if products["products"]:
        product_id = products["products"][0]["product_id"]
        order = order_product(token, product_id, quantity=1)
        print(f"Order placed: {order['order_id']}")

        # Review
        review = write_review(token, product_id, 5, "Great product")
        print(f"Review submitted: {review['review_id']}")
```

---

## API Reference

### Base URL
```
http://<YOUR_PUBLIC_IP>:8000
```

### Endpoints

#### Health Check
```http
GET /health
```
Response:
```json
{
  "status": "healthy",
  "service": "ecommerce-mcp-server",
  "version": "1.0.0"
}
```

#### Authentication
```http
POST /auth/login
Content-Type: application/json

{
  "email": "demo1@example.com",
  "password": "Demo123!"
}
```
Response:
```json
{
  "access_token": "eyJ...",
  "token_type": "Bearer",
  "expires_in": 86400,
  "customer_id": "cust-001"
}
```

#### Search Products (Public)
```http
POST /tools/search_products
Content-Type: application/json

{
  "query": "laptop",
  "category": "Electronics",  // optional
  "min_price": 500,           // optional
  "max_price": 1500,          // optional
  "limit": 10                 // optional, default 10
}
```

#### Order Product (Auth Required)
```http
POST /tools/order_product
Content-Type: application/json
Authorization: Bearer <token>

{
  "product_id": "prod-e9075764",
  "quantity": 1
}
```

#### Write Review (Auth Required)
```http
POST /tools/write_product_review
Content-Type: application/json
Authorization: Bearer <token>

{
  "product_id": "prod-e9075764",
  "rating": 5,
  "review_text": "Excellent product!"
}
```

#### Get Order History (Auth Required)
```http
POST /tools/get_order_history
Content-Type: application/json
Authorization: Bearer <token>

{
  "limit": 10  // optional
}
```

#### Initiate Return (Auth Required)
```http
POST /tools/initiate_return
Content-Type: application/json
Authorization: Bearer <token>

{
  "order_id": "ord-abc123",
  "reason": "Changed my mind"
}
```

---

## Troubleshooting

### Common Issues

#### 1. Docker Build Fails
```bash
# Check Docker is running
docker info

# Check disk space
df -h

# Build with no cache
docker build --no-cache -t ecommerce-mcp-server .
```

#### 2. ECS Task Keeps Restarting
```bash
# Check CloudWatch logs
aws logs tail /ecs/ecommerce-mcp-server --follow --region us-west-2

# Check task stopped reason
aws ecs describe-tasks \
  --cluster ecommerce-mcp-cluster \
  --tasks <TASK_ARN> \
  --query 'tasks[0].stoppedReason'
```

#### 3. Cannot Connect to Endpoint
```bash
# Verify security group allows port 8000
aws ec2 describe-security-groups --group-ids <SG_ID> \
  --query 'SecurityGroups[0].IpPermissions'

# Check task has public IP
aws ecs describe-tasks \
  --cluster ecommerce-mcp-cluster \
  --tasks <TASK_ARN> \
  --query 'tasks[0].attachments'
```

#### 4. Authentication Fails
```bash
# Verify Cognito user exists
aws cognito-idp admin-get-user \
  --user-pool-id <USER_POOL_ID> \
  --username demo1@example.com

# Test auth endpoint directly
curl -X POST http://<IP>:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "demo1@example.com", "password": "Demo123!"}'
```

#### 5. Force New Deployment
```bash
aws ecs update-service \
  --cluster ecommerce-mcp-cluster \
  --service ecommerce-mcp-service \
  --force-new-deployment \
  --region us-west-2
```

---

## Cost Estimation

### Monthly Costs (Demo Scale)

| Service | Configuration | Est. Cost |
|---------|---------------|-----------|
| ECS Fargate | 1 task, 0.25 vCPU, 512MB | $9 |
| DynamoDB | On-demand, <1GB | $5-10 |
| Cognito | <1000 MAU | Free |
| ECR | <1GB storage | $0.10 |
| CloudWatch Logs | <1GB | $1 |
| **Total** | | **~$15-20/month** |

### Cost Optimization Tips

1. **Stop ECS when not in use:**
   ```bash
   aws ecs update-service \
     --cluster ecommerce-mcp-cluster \
     --service ecommerce-mcp-service \
     --desired-count 0
   ```

2. **Use DynamoDB provisioned capacity** for predictable workloads

3. **Set CloudWatch log retention:**
   ```bash
   aws logs put-retention-policy \
     --log-group-name /ecs/ecommerce-mcp-server \
     --retention-in-days 7
   ```

---

## Demo Accounts

| Email | Password | Customer ID |
|-------|----------|-------------|
| demo1@example.com | Demo123! | cust-001 |
| demo2@example.com | Demo123! | cust-002 |
| demo3@example.com | Demo123! | cust-003 |
| ... | ... | ... |
| demo10@example.com | Demo123! | cust-010 |

---

## Clean Up Resources

To avoid ongoing charges, delete all resources:

```bash
# Delete ECS service and cluster
aws ecs update-service --cluster ecommerce-mcp-cluster \
  --service ecommerce-mcp-service --desired-count 0
aws ecs delete-service --cluster ecommerce-mcp-cluster \
  --service ecommerce-mcp-service --force
aws ecs delete-cluster --cluster ecommerce-mcp-cluster

# Delete security group
aws ec2 delete-security-group --group-id <SG_ID>

# Delete IAM roles
aws iam detach-role-policy --role-name ecsTaskRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess
aws iam detach-role-policy --role-name ecsTaskRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonCognitoPowerUser
aws iam delete-role --role-name ecsTaskRole

aws iam detach-role-policy --role-name ecsTaskExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
aws iam delete-role --role-name ecsTaskExecutionRole

# Delete CDK stack (removes DynamoDB, Cognito, ECR)
cd ecommerce-mcp-cdk
npx cdk destroy
```

---

## Support

For issues and questions:
- Check the [Troubleshooting](#troubleshooting) section
- Review CloudWatch logs for error details
- Verify IAM permissions and security group rules

---

**Version:** 1.0.0
**Last Updated:** January 2026
