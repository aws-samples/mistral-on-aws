"""
Cognito Stack for E-Commerce MCP Server

This stack creates:
- AWS Cognito User Pool with custom attributes (customer_id)
- Cognito Hosted UI Domain for OAuth browser flow
- App Client with OAuth 2.0 and USER_PASSWORD_AUTH flows
- Supports multi-client authentication (Claude Desktop, Mistral AI Studio, Strands Agents)
"""

from aws_cdk import (
    Stack,
    RemovalPolicy,
    CfnOutput,
    Duration,
    aws_cognito as cognito,
)
from constructs import Construct


class CognitoStack(Stack):
    """CDK Stack for Cognito User Pool and authentication"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ============================================================
        # Cognito User Pool
        # ============================================================
        self.user_pool = cognito.UserPool(
            self, "EcommerceUserPool",
            user_pool_name="ecommerce-mcp-users",
            self_sign_up_enabled=False,  # Admin creates demo users only
            sign_in_aliases=cognito.SignInAliases(
                email=True,
                username=False  # Use email as username
            ),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(
                    required=True,
                    mutable=True
                ),
                given_name=cognito.StandardAttribute(
                    required=True,
                    mutable=True
                ),
                family_name=cognito.StandardAttribute(
                    required=True,
                    mutable=True
                )
            ),
            custom_attributes={
                "customer_id": cognito.StringAttribute(
                    mutable=False  # Immutable once set
                )
            },
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=False  # Simplified for demo
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            removal_policy=RemovalPolicy.DESTROY  # Demo only - will delete users on stack deletion
        )

        # ============================================================
        # Cognito Hosted UI Domain (for OAuth browser flow)
        # ============================================================
        # Note: Domain prefix must be globally unique across all AWS accounts
        self.user_pool_domain = self.user_pool.add_domain(
            "CognitoDomain",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix="ecommerce-mcp-demo"  # Change this if domain is already taken
            )
        )

        # ============================================================
        # App Client (for MCP clients)
        # ============================================================
        self.app_client = self.user_pool.add_client(
            "EcommerceMcpClient",
            user_pool_client_name="mcp-client",
            auth_flows=cognito.AuthFlow(
                user_password=True,  # Enable USER_PASSWORD_AUTH flow (for Basic Auth)
                custom=False,
                user_srp=True  # Secure Remote Password
            ),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(
                    authorization_code_grant=True,  # For browser OAuth flow (Claude Desktop)
                    implicit_code_grant=False  # Not recommended for security
                ),
                scopes=[
                    cognito.OAuthScope.EMAIL,
                    cognito.OAuthScope.OPENID,
                    cognito.OAuthScope.PROFILE
                ],
                callback_urls=[
                    "http://localhost:8080/callback",      # Claude Desktop callback
                    "claudeapp://oauth/callback",          # Claude Desktop custom URI
                    "https://mistral.ai/oauth/callback",   # Mistral AI Studio (example)
                    "http://localhost:3000/callback"       # Local testing
                ],
                logout_urls=[
                    "http://localhost:8080/logout",
                    "https://mistral.ai/logout"
                ]
            ),
            generate_secret=False,  # Public client (no secret needed for mobile/desktop apps)
            access_token_validity=Duration.hours(24),
            id_token_validity=Duration.hours(24),
            refresh_token_validity=Duration.days(30),
            prevent_user_existence_errors=True  # Security best practice
        )

        # ============================================================
        # CloudFormation Outputs
        # ============================================================
        CfnOutput(self, "UserPoolId",
                  value=self.user_pool.user_pool_id,
                  description="Cognito User Pool ID",
                  export_name="EcommerceMcpUserPoolId")

        CfnOutput(self, "UserPoolArn",
                  value=self.user_pool.user_pool_arn,
                  description="Cognito User Pool ARN",
                  export_name="EcommerceMcpUserPoolArn")

        CfnOutput(self, "UserPoolClientId",
                  value=self.app_client.user_pool_client_id,
                  description="Cognito App Client ID",
                  export_name="EcommerceMcpClientId")

        CfnOutput(self, "CognitoDomainPrefix",
                  value="ecommerce-mcp-demo",
                  description="Cognito Hosted UI domain prefix")

        CfnOutput(self, "CognitoHostedUIUrl",
                  value=f"https://ecommerce-mcp-demo.auth.{self.region}.amazoncognito.com",
                  description="Cognito Hosted UI base URL")

        CfnOutput(self, "AuthorizationEndpoint",
                  value=f"https://ecommerce-mcp-demo.auth.{self.region}.amazoncognito.com/oauth2/authorize",
                  description="OAuth 2.0 authorization endpoint")

        CfnOutput(self, "TokenEndpoint",
                  value=f"https://ecommerce-mcp-demo.auth.{self.region}.amazoncognito.com/oauth2/token",
                  description="OAuth 2.0 token endpoint")

        CfnOutput(self, "UserInfoEndpoint",
                  value=f"https://ecommerce-mcp-demo.auth.{self.region}.amazoncognito.com/oauth2/userInfo",
                  description="OAuth 2.0 userInfo endpoint")

        CfnOutput(self, "LogoutEndpoint",
                  value=f"https://ecommerce-mcp-demo.auth.{self.region}.amazoncognito.com/logout",
                  description="OAuth 2.0 logout endpoint")

        # Configuration examples for different clients
        CfnOutput(self, "ClaudeDesktopConfig",
                  value=f'{{"url":"https://YOUR-ENDPOINT.agentcore.aws","auth":{{"type":"oauth2","authorization_endpoint":"https://ecommerce-mcp-demo.auth.{self.region}.amazoncognito.com/oauth2/authorize","token_endpoint":"https://ecommerce-mcp-demo.auth.{self.region}.amazoncognito.com/oauth2/token","client_id":"' + self.app_client.user_pool_client_id + '"}}}}',
                  description="Claude Desktop MCP server configuration (replace YOUR-ENDPOINT)")
