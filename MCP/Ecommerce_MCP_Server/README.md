# E-Commerce MCP Server

A production-ready MCP (Model Context Protocol) server for e-commerce operations using **streamable HTTP transport**. Designed for AI agents like Strands Agents and Mistral AI Studio.

## Features

### MCP Tools (6 Tools)

| Tool | Auth Required | Description |
|------|---------------|-------------|
| `search_products` | No | Search product catalog by name, category, or price range |
| `get_product_reviews` | No | Get product reviews with ratings |
| `order_product` | Yes | Place orders for products |
| `write_product_review` | Yes | Submit product reviews (1-5 stars) |
| `get_order_history` | Yes | View your order history |
| `initiate_return` | Yes | Request returns for orders |

### Authentication

Two authentication methods supported:

- **Bearer Token** - Get JWT token from `/auth/login`, pass as `Authorization: Bearer <token>`
- **Basic Auth** - Pass `Authorization: Basic <base64(email:password)>` header

### Architecture

- **Streamable HTTP MCP** - Native MCP protocol over HTTP (port 8000)
- **AWS Cognito** - User authentication and JWT token management
- **Amazon DynamoDB** - Data persistence (5 tables)
- **ECS Fargate** - Serverless container deployment

---

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+ (for CDK)
- AWS CLI configured with credentials
- Docker
- AWS CDK CLI: `npm install -g aws-cdk`

### 1. Deploy Infrastructure

```bash
cd ecommerce-mcp-cdk

# Install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Bootstrap CDK (first time only)
export AWS_REGION=us-west-2
cdk bootstrap

# Deploy all stacks
cdk deploy --all

# Note the outputs: UserPoolId, ClientId, table names
```

### 2. Load Demo Data

```bash
cd data
python generate_data.py
python load_data.py --region us-west-2

cd ../scripts
python create_cognito_users.py --region us-west-2
```

### 3. Deploy MCP Server

```bash
cd ../../mcp_server

# Build Docker image
docker build -t ecommerce-mcp-server .

# Push to ECR and deploy to ECS Fargate
# See USER_GUIDE.md for detailed deployment steps
```

---

## Demo Credentials

| Email | Password | Customer ID |
|-------|----------|-------------|
| demo1@example.com | Demo123! | cust-001 |
| demo2@example.com | Demo123! | cust-002 |
| ... | ... | ... |
| demo10@example.com | Demo123! | cust-010 |

---

## Client Integration

### Strands Agents

```python
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent
from strands.tools.mcp import MCPClient
import requests

# Get authentication token
response = requests.post(
    "http://your-server:8000/auth/login",
    json={"email": "demo1@example.com", "password": "Demo123!"}
)
token = response.json()["access_token"]

# Create MCP client with authentication
mcp_client = MCPClient(
    lambda: streamablehttp_client(
        url="http://your-server:8000/mcp",
        headers={"Authorization": f"Bearer {token}"}
    )
)

# Use with Strands Agent
with mcp_client:
    tools = mcp_client.list_tools_sync()
    agent = Agent(
        tools=tools,
        system_prompt="You are a helpful shopping assistant."
    )
    response = agent("Search for laptops under $1500")
    print(response)
```

### Mistral AI Studio

Configure in Settings:

1. **MCP Server URL**: `http://your-server:8000/mcp`
2. **Authentication**: Basic Auth
3. **Username**: `demo1@example.com`
4. **Password**: `Demo123!`

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/auth/login` | POST | Get access token |
| `/mcp` | POST | MCP protocol endpoint |

### Authentication

```bash
# Get access token
curl -X POST http://your-server:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "demo1@example.com", "password": "Demo123!"}'

# Response
{
  "access_token": "eyJhbGc...",
  "token_type": "Bearer",
  "expires_in": 86400,
  "customer_id": "cust-001"
}
```

---

## Architecture Overview

```
+------------------+     +-------------------+
|  Strands Agent   |     | Mistral AI Studio |
+--------+---------+     +---------+---------+
         |                         |
         |   Streamable HTTP MCP   |
         +------------+------------+
                      |
         +------------v------------+
         |   MCP Server (:8000)    |
         |   - /health             |
         |   - /auth/login         |
         |   - /mcp (MCP protocol) |
         +------------+------------+
                      |
    +-----------------+------------------+
    |                 |                  |
+---v---+       +-----v-----+      +-----v-----+
|Cognito|       | DynamoDB  |      | DynamoDB  |
| Auth  |       | Products  |      | Orders    |
+-------+       +-----------+      +-----------+
```


---
## Sample Questions

  Product Search (Public)

  - "Search for laptops under ` $1500` "
  - "Find electronics between ` $100`  and ` $500` "
  - "Search for products in the Home category"

  Product Reviews (Public)

  - "Show me reviews for the laptop I just found"
  - "Are there any 5-star reviews for that product?"

  Order History (Authenticated)

  - "Show me my purchase history"
  - "What have I bought recently?"
  - "Show me my last 5 orders"

  Place Orders (Authenticated)

  - "Order that laptop for me"
  - "Buy 2 of the wireless headphones"

  Write Reviews (Authenticated)

  - "Write a 5-star review for my last purchase saying it was excellent quality"

  Returns (Authenticated)

  - "Start a return - the product doesn't match the description"

  Multi-Turn Conversations

  👤 User: Search for laptops
  
  👤 User: Show me reviews for the first one
  
  👤 User: Order it for me
  
  👤 User: Now show my order history
  
  👤 User: Write a 5-star review saying great laptop


  
---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Server port | 8000 |
| `AWS_REGION` | AWS region | us-west-2 |
| `COGNITO_USER_POOL_ID` | Cognito User Pool ID | Required |
| `COGNITO_CLIENT_ID` | Cognito App Client ID | Required |
| `PRODUCTS_TABLE` | DynamoDB products table | ecommerce-products |
| `CUSTOMERS_TABLE` | DynamoDB customers table | ecommerce-customers |
| `ORDERS_TABLE` | DynamoDB orders table | ecommerce-orders |
| `REVIEWS_TABLE` | DynamoDB reviews table | ecommerce-reviews |
| `RETURNS_TABLE` | DynamoDB returns table | ecommerce-returns |


---

## Security

- Cognito-managed password hashing
- JWT token authentication with 24-hour expiration
- Context-based user isolation (each user sees only their data)
- No secrets in code or logs

---

## Documentation

- [User Guide](./USER_GUIDE.md) - Detailed deployment guide
- [Examples](./examples/README.md) - Python integration examples
- [CDK Setup](./ecommerce-mcp-cdk/README.md) - Infrastructure deployment

---

## License

This is a demo project for educational purposes.

---

**Built with:** FastMCP, AWS Cognito, DynamoDB, ECS Fargate
**Version:** 2.0.0
**Last Updated:** 2026-01-06
