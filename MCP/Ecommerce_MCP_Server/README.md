# E-Commerce MCP Server on Amazon Bedrock AgentCore Runtime

A production-ready MCP (Model Context Protocol) server for e-commerce operations, hosted on **Amazon Bedrock AgentCore Runtime** with JWT authentication enforced at the infrastructure layer.

## Features

### MCP Tools (6 Tools)

| Tool | Description |
|------|-------------|
| `search_products` | Search catalog by keyword, category, price, or stock availability |
| `get_product_reviews` | Get product reviews with ratings |
| `order_product` | Place orders for products |
| `write_product_review` | Submit product reviews (1-5 stars) |
| `get_order_history` | View your order history |
| `initiate_return` | Request returns for orders |

### Authentication — Handled by AgentCore Runtime

Authentication is enforced **before requests reach the server**. AgentCore Runtime validates:
- JWT signature (RS256) using Cognito OIDC discovery
- Token issuer and audience
- `allowedClients` (Cognito App Client ID)

If the token is missing or invalid, AgentCore returns `401` before the server code runs. The server reads `custom:customer_id` from the validated token using one of two methods depending on token type:
- **API Token (USER_PASSWORD_AUTH):** `cognito.get_user(AccessToken=token)` — token includes the required admin scope
- **OAuth 2.1 (Authorization Code):** decodes the JWT to extract `username` + `user_pool_id`, then calls `cognito.admin_get_user()` via IAM — these tokens carry only OIDC scopes and cannot call `get_user()` directly

**Basic Auth is not supported.** Clients authenticate with a Cognito Bearer JWT.

### Architecture

```
Client (Strands Agent / Mistral AI Studio)
    │  Authorization: Bearer <Cognito access token>
    ▼
AgentCore Runtime  ←── validates JWT: signature, issuer, audience, allowedClients
    │               ←── forwards request + Authorization header to server
    ▼
UserContextMiddleware (server.py)
    │  calls cognito.get_user(AccessToken=token) → custom:customer_id
    ▼
MCP Tool  →  DynamoDB
```

**AWS Services:**
- **Amazon Bedrock AgentCore Runtime** — managed container hosting, JWT auth enforcement, on-demand scaling
- **AWS CodeBuild** — cloud-side ARM64 image build (no local Docker required)
- **Amazon ECR** — container image registry
- **Amazon Cognito** — OAuth 2.0 / OIDC provider (JWT issuer + user attributes)
- **Amazon DynamoDB** — 5-table data backend (products, customers, orders, reviews, returns)
- **AWS CloudWatch** — logs and observability

---

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+ (for CDK)
- AWS CLI configured with credentials and a bootstrapped CDK environment
- `bedrock-agentcore-starter-toolkit` CLI: `pip install bedrock-agentcore-starter-toolkit`
- AWS CDK CLI: `npm install -g aws-cdk`

### 1. Deploy Infrastructure

```bash
cd ecommerce-mcp-cdk
pip install -r requirements.txt

# Bootstrap CDK (first time only)
cdk bootstrap

# Deploy all 4 stacks: DynamoDB, Cognito, DataLoader, AgentCoreRuntime
cdk deploy --all --require-approval never
```

Note the four outputs from `EcommerceMcpAgentCoreStack`:
- `ExecutionRoleArn`
- `EcrUri`
- `CognitoDiscoveryUrl`
- `CognitoClientId`

These are also stored in SSM under `/ecommerce-mcp/*` for convenience.

### 2. Create Demo Users

```bash
python scripts/create_cognito_users.py --region us-west-2
```

### 3. Configure AgentCore Runtime

Run from the `mcp_server/` directory:

```bash
cd ../mcp_server

agentcore configure \
  -e server.py \
  -p MCP \
  -n ecommerce_mcp_server \
  -er $(aws ssm get-parameter --name /ecommerce-mcp/execution-role-arn --query Parameter.Value --output text) \
  -ecr $(aws ssm get-parameter --name /ecommerce-mcp/ecr-uri --query Parameter.Value --output text) \
  -ac "{\"customJWTAuthorizer\":{\"discoveryUrl\":\"$(aws ssm get-parameter --name /ecommerce-mcp/cognito-discovery-url --query Parameter.Value --output text)\",\"allowedClients\":[\"$(aws ssm get-parameter --name /ecommerce-mcp/cognito-client-id --query Parameter.Value --output text)\",\"$(aws ssm get-parameter --name /ecommerce-mcp/mistral-client-id --query Parameter.Value --output text)\"]}}" \
  -rha "Authorization" \
  -r us-west-2 \
  --non-interactive
```

> **Note:** Agent names must use underscores, not hyphens (`ecommerce_mcp_server`, not `ecommerce-mcp-server`).

### 4. Deploy to AgentCore Runtime

```bash
agentcore deploy \
  --env AWS_REGION=us-west-2 \
  --env PRODUCTS_TABLE=ecommerce-products \
  --env CUSTOMERS_TABLE=ecommerce-customers \
  --env ORDERS_TABLE=ecommerce-orders \
  --env REVIEWS_TABLE=ecommerce-reviews \
  --env RETURNS_TABLE=ecommerce-returns
```

`agentcore deploy` (default mode) automatically:
1. Creates a CodeBuild project in your account to build the ARM64 Docker image in the cloud
2. Pushes the image to ECR
3. Calls `CreateAgentRuntime` to register and launch the runtime

No local Docker installation is required.

The command outputs the Runtime ARN:
```
arn:aws:bedrock-agentcore:<region>:<account>:runtime/ecommerce_mcp_server-<id>
```

### 5. Validate

```bash
python scripts/test_auth_methods.py \
  --runtime-arn <ARN from step 4> \
  --region us-west-2
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

## Connecting from Mistral AI Studio

### API Token (working today)

Run the token generation script to get a fresh Cognito Bearer token:

```bash
python get_mistral_token.py            # demo1@example.com (default)
python get_mistral_token.py --user demo3
python get_mistral_token.py --email you@company.com --password YourPass
```

The script reads all account-specific values from SSM at runtime — no hardcoded IDs.
The token and Connector Server URL are printed automatically.

Configure the Mistral custom MCP connector:

| Field | Value |
|-------|-------|
| Connector Server | *(printed by `get_mistral_token.py` — derived from SSM and agentcore status)* |
| Authentication Method | API Token Authentication |
| Header name | `Authorization` |
| Header type | `Bearer` |
| Header value | *(token printed by script, also saved to `mistral_token.txt`)* |

To get the Connector Server URL manually:
```bash
RUNTIME_ARN=$(aws ssm get-parameter \
  --name /ecommerce-mcp/agentcore-runtime-arn \
  --query Parameter.Value --output text)

python3 -c "
import urllib.parse
arn = '$RUNTIME_ARN'
print('https://bedrock-agentcore.us-west-2.amazonaws.com/runtimes/'
      + urllib.parse.quote(arn, safe='') + '/invocations')
"
# Or simply:
agentcore status   # shows Agent ARN
```

Tokens expire after **24 hours**. Rerun the script and update the connector value to refresh.

### OAuth 2.1 (working)

OAuth 2.1 is fully supported. When Connect is clicked, Mistral opens a Cognito login popup — the user logs in once and Mistral handles token refresh automatically.

Configure the Mistral custom MCP connector:

| Field | Value |
|-------|-------|
| Connector Server | *(same URL as API Token — derived from `agentcore status` or SSM)* |
| Authentication Method | OAuth 2.1 |
| Client ID | *(from `aws ssm get-parameter --name /ecommerce-mcp/mistral-client-id`)* |
| Client Secret | *(from `aws cognito-idp describe-user-pool-client` — see Cognito App Clients section)* |

> **OAuth 2.1 vs API Token:** Both connect to the same AgentCore endpoint. OAuth 2.1 eliminates the 24-hour manual token rotation — Mistral handles token acquisition and refresh automatically via the Cognito Hosted UI.

---

## Client Integration

### Strands Agents

```python
import boto3
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent
from strands.tools.mcp import MCPClient

# Read account-specific values from SSM (no hardcoded IDs)
ssm = boto3.client('ssm', region_name='us-west-2')
CLIENT_ID   = ssm.get_parameter(Name='/ecommerce-mcp/cognito-client-id')['Parameter']['Value']
RUNTIME_ARN = ssm.get_parameter(Name='/ecommerce-mcp/agentcore-runtime-arn')['Parameter']['Value']

# Get a Cognito Bearer token
cognito = boto3.client('cognito-idp', region_name='us-west-2')
resp = cognito.initiate_auth(
    ClientId=CLIENT_ID,
    AuthFlow='USER_PASSWORD_AUTH',
    AuthParameters={'USERNAME': 'demo1@example.com', 'PASSWORD': 'Demo123!'}
)
token = resp['AuthenticationResult']['AccessToken']

import urllib.parse
RUNTIME_ENDPOINT = (
    "https://bedrock-agentcore.us-west-2.amazonaws.com/runtimes/"
    + urllib.parse.quote(RUNTIME_ARN, safe='') + "/invocations"
)

mcp_client = MCPClient(
    lambda: streamablehttp_client(
        url=RUNTIME_ENDPOINT,
        headers={"Authorization": f"Bearer {token}"}
    )
)

with mcp_client:
    tools = mcp_client.list_tools_sync()
    agent = Agent(tools=tools, system_prompt="You are a helpful shopping assistant.")
    response = agent("Show me all electronics in stock under $500")
    print(response)
```

---

## Tool Reference

### `search_products`

```
search_products(
    query: str = "",          # keyword search against name/description
    category: str = None,     # "Electronics" | "Clothing" | "Books" | "Home"
    min_price: float = None,
    max_price: float = None,
    in_stock_only: bool = False,  # True = only products with stock_quantity > 0
    limit: int = 10
)
```

> **Important:** `in_stock_only=True` filters by `stock_quantity > 0`. Do **not** pass `"in stock"` as a `query` string — that performs a text search against product names and will return 0 results.

Examples:
- All available products: `search_products(in_stock_only=True)`
- Electronics in stock: `search_products(category="Electronics", in_stock_only=True)`
- Laptops under $1500: `search_products(query="laptop", max_price=1500)`

---

## How the Server is Deployed

The container runs on **Amazon Bedrock AgentCore Runtime** — a managed serverless container service distinct from ECS, Lambda, or Fargate:

- **On-demand execution**: container starts on first request (cold start ~10-20s), stays warm for subsequent calls
- **No infrastructure management**: no clusters, task definitions, security groups, or load balancers
- **ARM64 container**: built via CodeBuild, pushed to ECR, pulled by AgentCore at runtime
- **Stateless**: `stateless_http=True` in `mcp.http_app()` — required for AgentCore's request routing

## Transport: Streamable HTTP + SSE

The server uses MCP's **Streamable HTTP** transport. When a client sends `Accept: text/event-stream`, responses are SSE-formatted:

```
event: message
data: {"jsonrpc":"2.0","id":1,"result":{"tools":[...]}}
```

Clients must read the response as a stream and parse `data:` lines. Plain JSON is returned when the client sends only `Accept: application/json`.

---

## Cognito App Clients

Two app clients are provisioned in the Cognito User Pool. Retrieve their IDs from SSM or CDK outputs:

```bash
# API Token client (mcp-client)
aws ssm get-parameter --name /ecommerce-mcp/cognito-client-id \
  --query Parameter.Value --output text

# Mistral OAuth 2.1 client (mistral-oauth-client)
aws ssm get-parameter --name /ecommerce-mcp/mistral-client-id \
  --query Parameter.Value --output text

# Mistral OAuth 2.1 client secret (sensitive — never commit this)
aws cognito-idp describe-user-pool-client \
  --user-pool-id $(aws cloudformation describe-stacks \
    --stack-name EcommerceMcpCognitoStack \
    --query "Stacks[0].Outputs[?OutputKey=='UserPoolId'].OutputValue" \
    --output text) \
  --client-id $(aws ssm get-parameter --name /ecommerce-mcp/mistral-client-id \
    --query Parameter.Value --output text) \
  --query "UserPoolClient.ClientSecret" --output text
```

| Client name | Secret | Used for |
|-------------|--------|----------|
| mcp-client | No | API Token flow (`get_mistral_token.py`), Strands Agents |
| mistral-oauth-client | Yes | OAuth 2.1 flow (Mistral AI Studio) — fully working |

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Server port | 8000 |
| `AWS_REGION` | AWS region | us-west-2 |
| `PRODUCTS_TABLE` | DynamoDB products table | ecommerce-products |
| `CUSTOMERS_TABLE` | DynamoDB customers table | ecommerce-customers |
| `ORDERS_TABLE` | DynamoDB orders table | ecommerce-orders |
| `REVIEWS_TABLE` | DynamoDB reviews table | ecommerce-reviews |
| `RETURNS_TABLE` | DynamoDB returns table | ecommerce-returns |

---

## Security

- JWT signature, issuer, audience, and `allowedClients` validated by AgentCore (not server code)
- `custom:customer_id` extracted via `cognito.get_user()` (API Token) or `cognito.admin_get_user()` (OAuth 2.1) — both use IAM, not local JWT parsing
- Tool-level auth checks (`if customer_id == 'anonymous'`) provide defense in depth
- Per-request user isolation via `ContextVar`
- AgentCore has no "passthrough" mode — all requests require a valid Cognito Bearer token

---

## Documentation

- [User Guide](./USER_GUIDE.md) — Detailed deployment and troubleshooting guide
- [CDK Setup](./ecommerce-mcp-cdk/README.md) — Infrastructure stacks reference

---

**Built with:** FastMCP 3.x, Amazon Bedrock AgentCore Runtime, AWS Cognito, DynamoDB, CodeBuild, ECR
**Version:** 3.2.0
**Last Updated:** March 2026
