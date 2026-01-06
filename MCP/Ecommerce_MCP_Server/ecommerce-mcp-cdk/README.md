# E-Commerce MCP Server - CDK Infrastructure

This CDK application deploys the AWS infrastructure for the E-Commerce MCP Server.

## Architecture

### Stacks

1. **DynamoDBStack** - 5 DynamoDB tables with 8 Global Secondary Indexes
   - Products Table
   - Customers Table (1 GSI: email-index)
   - Orders Table (2 GSIs: customer_id-created_at-index, customer_id-product_id-index)
   - Reviews Table (3 GSIs: product_id-created_at-index, product_id-rating-index, customer_id-created_at-index)
   - Returns Table (2 GSIs: order_id-index, customer_id-created_at-index)

2. **CognitoStack** - AWS Cognito User Pool for authentication
   - User Pool with custom attributes (customer_id)
   - Cognito Hosted UI Domain for OAuth browser flow
   - App Client supporting OAuth 2.0 and USER_PASSWORD_AUTH
   - Multi-client support (Claude Desktop, Mistral AI Studio, Strands Agents)

3. **DataLoaderStack** - Custom resource for loading synthetic data
   - Lambda function to populate tables with demo data
   - Triggers automatically during stack creation

## Prerequisites

- Python 3.10+
- Node.js 18+ (for CDK CLI)
- AWS CLI configured with credentials
- AWS CDK CLI: `npm install -g aws-cdk`

## Setup

1. **Create virtual environment and install dependencies:**

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2. **Bootstrap CDK (first time only):**

```bash
export AWS_REGION=us-west-2  # Or your preferred region
cdk bootstrap aws://ACCOUNT_ID/$AWS_REGION
```

3. **Synthesize CloudFormation templates:**

```bash
cdk synth
```

4. **Deploy all stacks:**

```bash
cdk deploy --all
```

## Outputs

After deployment, the stack outputs will include:

- DynamoDB table names and ARNs
- Cognito User Pool ID and Client ID
- Cognito Hosted UI URLs (authorization, token, userInfo endpoints)
- Configuration examples for Claude Desktop

## Cost Estimate

Demo scale (~10 users, <1000 requests/month):
- DynamoDB: $5-10/month (on-demand pricing)
- Cognito: Free tier (<1000 MAU)
- Lambda (DataLoader): Negligible (<1 minute execution)

**Total: ~$5-10/month for infrastructure only**

(Note: AgentCore Runtime deployment costs additional $30-35/month)

## Cleanup

To delete all resources:

```bash
cdk destroy --all
```

**Warning:** This will permanently delete all data in DynamoDB tables.

## Next Steps

After deploying the CDK stacks:

1. Load synthetic data: `python data/generate_data.py && python data/load_data.py`
2. Create Cognito users: `python scripts/create_cognito_users.py`
3. Deploy MCP server to AgentCore Runtime
4. Configure MCP clients (Claude Desktop, Mistral AI Studio, etc.)

## Documentation

- [EPCC_PLAN.md](../EPCC_PLAN.md) - Complete implementation plan
- [EPCC_EXPLORE.md](../EPCC_EXPLORE.md) - Architecture exploration findings
- [EPCC_PRD.md](../EPCC_PRD.md) - Product requirements document
