"""
Authentication Module for E-Commerce MCP Server

Supports multiple authentication methods:
1. OAuth Bearer Token (Cognito JWT) - for Claude Desktop OAuth flow
2. Basic Auth (username:password) - for Mistral AI Studio and Strands Agents
3. Direct authentication via /auth/login endpoint

All methods validate against AWS Cognito User Pools and extract customer_id
from custom attributes.
"""

import os
import base64
import json
from typing import Optional, Dict
import boto3
import requests
from jose import jwt, JWTError
from botocore.exceptions import ClientError


class AuthenticationError(Exception):
    """Raised when authentication fails"""
    pass


class CognitoAuthenticator:
    """
    Handles authentication with AWS Cognito User Pools

    Supports:
    - Bearer token validation (OAuth 2.0)
    - Username/password authentication (USER_PASSWORD_AUTH)
    - Token refresh
    """

    def __init__(
        self,
        region: str,
        user_pool_id: str,
        client_id: str
    ):
        self.region = region
        self.user_pool_id = user_pool_id
        self.client_id = client_id
        self.cognito_client = boto3.client('cognito-idp', region_name=region)

        # Get JWKS keys for token validation
        self.jwks_url = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json"
        self.jwks_keys = None

    def _get_jwks_keys(self) -> dict:
        """Fetch JWKS keys for token validation (cached)"""
        if not self.jwks_keys:
            response = requests.get(self.jwks_url)
            response.raise_for_status()
            self.jwks_keys = response.json()
        return self.jwks_keys

    async def validate_token(self, access_token: str) -> Dict[str, str]:
        """
        Validate Cognito access token and extract user information

        Args:
            access_token: JWT access token from Cognito

        Returns:
            dict: User context with customer_id, email, etc.

        Raises:
            AuthenticationError: If token is invalid
        """
        try:
            # Get JWKS keys
            jwks = self._get_jwks_keys()

            # Decode token header to get kid
            unverified_header = jwt.get_unverified_header(access_token)
            kid = unverified_header['kid']

            # Find matching key
            key = None
            for jwk_key in jwks['keys']:
                if jwk_key['kid'] == kid:
                    key = jwk_key
                    break

            if not key:
                raise AuthenticationError("Unable to find matching key")

            # Verify and decode token
            payload = jwt.decode(
                access_token,
                key,
                algorithms=['RS256'],
                audience=self.client_id,
                issuer=f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}"
            )

            # Get full user info (including custom attributes)
            user_info = self.cognito_client.get_user(AccessToken=access_token)

            # Extract attributes
            user_context = {
                'username': user_info['Username'],
                'email': None,
                'customer_id': None,
                'given_name': None,
                'family_name': None
            }

            for attr in user_info['UserAttributes']:
                if attr['Name'] == 'email':
                    user_context['email'] = attr['Value']
                elif attr['Name'] == 'custom:customer_id':
                    user_context['customer_id'] = attr['Value']
                elif attr['Name'] == 'given_name':
                    user_context['given_name'] = attr['Value']
                elif attr['Name'] == 'family_name':
                    user_context['family_name'] = attr['Value']

            if not user_context['customer_id']:
                raise AuthenticationError("Missing customer_id in token")

            return user_context

        except JWTError as e:
            raise AuthenticationError(f"Invalid token: {str(e)}")
        except ClientError as e:
            raise AuthenticationError(f"Token validation failed: {e.response['Error']['Message']}")

    async def authenticate_with_password(
        self,
        email: str,
        password: str
    ) -> Dict[str, str]:
        """
        Authenticate user with email and password (USER_PASSWORD_AUTH flow)

        Args:
            email: User email (username)
            password: User password

        Returns:
            dict: Contains access_token, refresh_token, expires_in, and user_context

        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            response = self.cognito_client.initiate_auth(
                ClientId=self.client_id,
                AuthFlow='USER_PASSWORD_AUTH',
                AuthParameters={
                    'USERNAME': email,
                    'PASSWORD': password
                }
            )

            if 'AuthenticationResult' not in response:
                raise AuthenticationError("Authentication failed - no result returned")

            auth_result = response['AuthenticationResult']
            access_token = auth_result['AccessToken']

            # Get user context from token
            user_context = await self.validate_token(access_token)

            return {
                'access_token': access_token,
                'id_token': auth_result.get('IdToken'),
                'refresh_token': auth_result.get('RefreshToken'),
                'expires_in': auth_result.get('ExpiresIn', 3600),
                'token_type': 'Bearer',
                'user_context': user_context
            }

        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_msg = e.response['Error']['Message']

            if error_code == 'NotAuthorizedException':
                raise AuthenticationError("Invalid email or password")
            elif error_code == 'UserNotFoundException':
                raise AuthenticationError("User not found")
            else:
                raise AuthenticationError(f"Authentication failed: {error_msg}")


# ============================================================================
# Middleware Functions for FastMCP
# ============================================================================

async def authenticate_request(authorization: Optional[str]) -> Dict[str, str]:
    """
    Flexible authentication middleware that accepts multiple auth methods

    Supports:
    1. Bearer <token> - OAuth 2.0 access token from Cognito
    2. Basic <credentials> - Base64-encoded email:password

    Args:
        authorization: Authorization header value

    Returns:
        dict: User context with customer_id, email, etc.

    Raises:
        AuthenticationError: If authentication fails
    """
    if not authorization:
        raise AuthenticationError("Missing Authorization header")

    # Initialize authenticator
    region = os.environ.get('AWS_REGION', 'us-west-2')
    user_pool_id = os.environ.get('COGNITO_USER_POOL_ID')
    client_id = os.environ.get('COGNITO_CLIENT_ID')

    if not user_pool_id or not client_id:
        raise AuthenticationError("Cognito configuration not found")

    authenticator = CognitoAuthenticator(region, user_pool_id, client_id)

    # Method 1: Bearer token (OAuth)
    if authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        return await authenticator.validate_token(token)

    # Method 2: Basic Auth (username:password)
    elif authorization.startswith("Basic "):
        try:
            credentials = base64.b64decode(
                authorization.replace("Basic ", "")
            ).decode('utf-8')

            if ':' not in credentials:
                raise AuthenticationError("Invalid Basic Auth format")

            email, password = credentials.split(':', 1)
            auth_result = await authenticator.authenticate_with_password(email, password)
            return auth_result['user_context']

        except Exception as e:
            raise AuthenticationError(f"Basic Auth failed: {str(e)}")

    else:
        raise AuthenticationError("Unsupported authentication method")


async def validate_cognito_token(token: str) -> Dict[str, str]:
    """
    Convenience function to validate Cognito token

    Args:
        token: JWT access token

    Returns:
        dict: User context

    Raises:
        AuthenticationError: If validation fails
    """
    region = os.environ.get('AWS_REGION', 'us-west-2')
    user_pool_id = os.environ.get('COGNITO_USER_POOL_ID')
    client_id = os.environ.get('COGNITO_CLIENT_ID')

    authenticator = CognitoAuthenticator(region, user_pool_id, client_id)
    return await authenticator.validate_token(token)
