"""
AgentCore Runtime Stack for E-Commerce MCP Server

This stack provisions the supporting AWS infrastructure for hosting
the MCP server on Amazon Bedrock AgentCore Runtime:

- IAM execution role (bedrock-agentcore.amazonaws.com trust)
- ECR repository for the server container image
- SSM Parameters with values needed by `agentcore configure`
"""

from aws_cdk import (
    Stack,
    RemovalPolicy,
    CfnOutput,
    aws_iam as iam,
    aws_ecr as ecr,
    aws_ssm as ssm,
)
from constructs import Construct


class AgentCoreRuntimeStack(Stack):
    """CDK Stack for AgentCore Runtime supporting infrastructure"""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        products_table,
        customers_table,
        orders_table,
        reviews_table,
        returns_table,
        user_pool,
        app_client,
        mistral_client,
        region: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ============================================================
        # IAM Execution Role
        # ============================================================
        execution_role = iam.Role(
            self, "AgentCoreExecutionRole",
            role_name="AgentCoreExecutionRole",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            description="Execution role for E-Commerce MCP Server on AgentCore Runtime",
        )

        # DynamoDB permissions on all 5 tables
        table_arns = [
            products_table.table_arn,
            customers_table.table_arn,
            orders_table.table_arn,
            reviews_table.table_arn,
            returns_table.table_arn,
        ]
        execution_role.add_to_policy(
            iam.PolicyStatement(
                sid="DynamoDBAccess",
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:Query",
                    "dynamodb:Scan",
                ],
                resources=table_arns + [f"{arn}/index/*" for arn in table_arns],
            )
        )

        # ECR permissions (granted after repo is created — see below)

        # CloudWatch Logs permissions
        execution_role.add_to_policy(
            iam.PolicyStatement(
                sid="CloudWatchLogsAccess",
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=["arn:aws:logs:*:*:*"],
            )
        )

        # Cognito permissions to read custom:customer_id from access tokens.
        # GetUser      — for USER_PASSWORD_AUTH tokens (aws.cognito.signin.user.admin scope)
        # AdminGetUser — for OAuth 2.1 Authorization Code tokens (OIDC scopes only,
        #                no admin scope, so we fall back to IAM-based lookup)
        execution_role.add_to_policy(
            iam.PolicyStatement(
                sid="CognitoGetUser",
                actions=[
                    "cognito-idp:GetUser",
                    "cognito-idp:AdminGetUser",
                ],
                resources=["*"],
            )
        )

        # ============================================================
        # ECR Repository
        # Import if it already exists (created by a previous agentcore launch),
        # otherwise create it fresh.
        # ============================================================
        import boto3 as _boto3
        from botocore.exceptions import ClientError as _ClientError

        _ecr = _boto3.client('ecr', region_name=region)
        try:
            _ecr.describe_repositories(repositoryNames=["ecommerce-mcp-server"])
            _repo_exists = True
        except _ClientError:
            _repo_exists = False

        if _repo_exists:
            self.ecr_repo = ecr.Repository.from_repository_name(
                self, "EcrRepository",
                repository_name="ecommerce-mcp-server",
            )
        else:
            self.ecr_repo = ecr.Repository(
                self, "EcrRepository",
                repository_name="ecommerce-mcp-server",
                removal_policy=RemovalPolicy.DESTROY,
                empty_on_delete=True,
            )

        # Grant ECR pull permissions to the execution role
        execution_role.add_to_policy(
            iam.PolicyStatement(
                sid="EcrPullAccess",
                actions=[
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchGetImage",
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:GetAuthorizationToken",
                ],
                resources=["*"],
            )
        )

        # ============================================================
        # Derived values
        # ============================================================
        cognito_discovery_url = (
            f"https://cognito-idp.{region}.amazonaws.com/"
            f"{user_pool.user_pool_id}"
            f"/.well-known/openid-configuration"
        )
        ecr_uri = self.ecr_repo.repository_uri

        # ============================================================
        # SSM Parameters (consumed by `agentcore configure`)
        # ============================================================
        ssm.StringParameter(
            self, "SsmExecutionRoleArn",
            parameter_name="/ecommerce-mcp/execution-role-arn",
            string_value=execution_role.role_arn,
            description="AgentCore execution role ARN",
        )

        ssm.StringParameter(
            self, "SsmEcrUri",
            parameter_name="/ecommerce-mcp/ecr-uri",
            string_value=ecr_uri,
            description="ECR repository URI for MCP server image",
        )

        ssm.StringParameter(
            self, "SsmCognitoDiscoveryUrl",
            parameter_name="/ecommerce-mcp/cognito-discovery-url",
            string_value=cognito_discovery_url,
            description="Cognito OIDC discovery URL for AgentCore JWT authorizer",
        )

        ssm.StringParameter(
            self, "SsmCognitoClientId",
            parameter_name="/ecommerce-mcp/cognito-client-id",
            string_value=app_client.user_pool_client_id,
            description="Cognito app client ID for AgentCore JWT authorizer allowedClients",
        )

        ssm.StringParameter(
            self, "SsmMistralClientId",
            parameter_name="/ecommerce-mcp/mistral-client-id",
            string_value=mistral_client.user_pool_client_id,
            description="Mistral OAuth 2.1 app client ID for AgentCore JWT authorizer allowedClients",
        )

        # ============================================================
        # CloudFormation Outputs
        # ============================================================
        CfnOutput(self, "ExecutionRoleArn",
                  value=execution_role.role_arn,
                  description="AgentCore execution role ARN — pass to --execution-role")

        CfnOutput(self, "EcrUri",
                  value=ecr_uri,
                  description="ECR repository URI — pass to --ecr-uri")

        CfnOutput(self, "CognitoDiscoveryUrl",
                  value=cognito_discovery_url,
                  description="Cognito OIDC discovery URL — use in --authorizer-config discoveryUrl")

        CfnOutput(self, "CognitoClientId",
                  value=app_client.user_pool_client_id,
                  description="Cognito app client ID — use in --authorizer-config allowedClients")

        CfnOutput(self, "MistralClientId",
                  value=mistral_client.user_pool_client_id,
                  description="Mistral OAuth 2.1 client ID — also in --authorizer-config allowedClients")
