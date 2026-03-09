# E-Commerce MCP Server — CDK Infrastructure

This CDK application deploys the AWS infrastructure for the E-Commerce MCP Server on Amazon Bedrock AgentCore Runtime.

## Stacks

### Stack 1: `EcommerceMcpDynamoDBStack`

5 DynamoDB tables with PAY_PER_REQUEST billing:

| Table | Primary Key | GSIs |
|-------|-------------|------|
| `ecommerce-products` | `product_id` | — |
| `ecommerce-customers` | `customer_id` | `email-index` |
| `ecommerce-orders` | `order_id` | `customer_id-created_at-index`, `customer_id-product_id-index` |
| `ecommerce-reviews` | `review_id` | `product_id-created_at-index`, `product_id-rating-index`, `customer_id-created_at-index` |
| `ecommerce-returns` | `return_id` | `order_id-index`, `customer_id-created_at-index` |

### Stack 2: `EcommerceMcpCognitoStack`

- **User Pool** (`ecommerce-mcp-users`) with `custom:customer_id` attribute
- **Hosted UI Domain** (`ecommerce-mcp-demo.auth.<region>.amazoncognito.com`) for browser OAuth flows
- **App Client** supporting `USER_PASSWORD_AUTH` (for agent/script access) and Authorization Code Grant (for Claude Desktop)

Outputs used by AgentCore:
- `UserPoolId` — identifies the Cognito pool
- `UserPoolClientId` — used as `allowedClients` in the JWT authorizer
- `CognitoHostedUIUrl` — base URL for OAuth endpoints

### Stack 3: `EcommerceMcpDataLoaderStack`

Lambda-based custom resource that populates the DynamoDB tables with synthetic demo data (products, customers, orders, reviews, returns) during `cdk deploy`.

### Stack 4: `EcommerceMcpAgentCoreStack`

Supporting infrastructure for the AgentCore Runtime deployment:

**IAM Execution Role** (`AgentCoreExecutionRole`)
- Trust principal: `bedrock-agentcore.amazonaws.com`
- DynamoDB: `GetItem`, `PutItem`, `UpdateItem`, `Query`, `Scan` on all 5 tables (+ GSIs)
- ECR: `GetDownloadUrlForLayer`, `BatchGetImage`, `BatchCheckLayerAvailability`, `GetAuthorizationToken`
- CloudWatch Logs: `CreateLogGroup`, `CreateLogStream`, `PutLogEvents`
- Cognito: `cognito-idp:GetUser` (to read `custom:customer_id` from pre-validated tokens)

**ECR Repository** (`ecommerce-mcp-server`)
- Existing repositories are imported (`from_repository_name`) rather than recreated
- `agentcore deploy` pushes timestamped image tags here

**SSM Parameters** (consumed by `agentcore configure`):

| Parameter | Value |
|-----------|-------|
| `/ecommerce-mcp/execution-role-arn` | IAM execution role ARN |
| `/ecommerce-mcp/ecr-uri` | ECR repository URI |
| `/ecommerce-mcp/cognito-discovery-url` | `https://cognito-idp.<region>.amazonaws.com/<pool_id>/.well-known/openid-configuration` |
| `/ecommerce-mcp/cognito-client-id` | Cognito App Client ID |

**CloudFormation Outputs**: `ExecutionRoleArn`, `EcrUri`, `CognitoDiscoveryUrl`, `CognitoClientId`

---

## Setup

```bash
pip install -r requirements.txt

# Bootstrap CDK (once per account/region)
cdk bootstrap

# Synthesize to validate templates
cdk synth

# Deploy all stacks
cdk deploy --all --require-approval never
```

---

## Stack Dependencies

```
EcommerceMcpDynamoDBStack
EcommerceMcpCognitoStack
        ↓
EcommerceMcpDataLoaderStack
EcommerceMcpAgentCoreStack   ← depends on both DynamoDB + Cognito
```

---

## Outputs Reference

After `cdk deploy --all`, collect the AgentCore stack outputs:

```bash
aws cloudformation describe-stacks \
  --stack-name EcommerceMcpAgentCoreStack \
  --query "Stacks[0].Outputs" \
  --output table
```

Or read from SSM (same values, easier to script):

```bash
for p in execution-role-arn ecr-uri cognito-discovery-url cognito-client-id; do
  echo "/ecommerce-mcp/$p = $(aws ssm get-parameter --name /ecommerce-mcp/$p --query Parameter.Value --output text)"
done
```

---

## Cost Estimate

Demo scale (~10 users, ~1000 requests/month):

| Service | Cost |
|---------|------|
| DynamoDB (on-demand) | ~$5–10/month |
| Cognito (<1000 MAU) | Free tier |
| Lambda (DataLoader, runs once) | Negligible |
| ECR storage (~200 MB image) | ~$0.02/month |
| AgentCore Runtime | ~$30–35/month |
| CodeBuild (first deploy) | ~$0.01 |

**Total: ~$35–45/month**

---

## Cleanup

```bash
# Destroy all stacks and data
cdk destroy --all
```

**Warning:** `RemovalPolicy.DESTROY` is set on all tables and the ECR repo — all data will be deleted.

---

## Next Steps After CDK Deploy

1. Create Cognito demo users: `python scripts/create_cognito_users.py`
2. Configure AgentCore: `agentcore configure ...` (see [USER_GUIDE.md](../USER_GUIDE.md))
3. Deploy the server: `agentcore deploy`
4. Validate: `python scripts/test_auth_methods.py --runtime-arn <ARN>`
