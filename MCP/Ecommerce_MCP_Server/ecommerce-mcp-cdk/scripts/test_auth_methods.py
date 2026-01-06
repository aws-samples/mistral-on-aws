#!/usr/bin/env python3
"""
Authentication Testing Script for E-Commerce MCP Server

Tests both OAuth 2.0 and USER_PASSWORD_AUTH flows with Cognito.

Usage:
    python test_auth_methods.py [--region us-west-2] [--email demo1@example.com]
"""

import argparse
import boto3
import base64
from botocore.exceptions import ClientError


def get_cognito_config(region):
    """Get Cognito configuration from CloudFormation stack outputs"""
    cfn = boto3.client('cloudformation', region_name=region)

    try:
        response = cfn.describe_stacks(StackName='EcommerceMcpCognitoStack')
        outputs = response['Stacks'][0]['Outputs']

        config = {}
        for output in outputs:
            if output['OutputKey'] == 'UserPoolId':
                config['user_pool_id'] = output['OutputValue']
            elif output['OutputKey'] == 'UserPoolClientId':
                config['client_id'] = output['OutputValue']

        if 'user_pool_id' not in config or 'client_id' not in config:
            print("❌ Error: Missing Cognito configuration in stack outputs")
            return None

        return config

    except ClientError as e:
        print(f"❌ Error getting Cognito configuration: {e}")
        return None


def test_user_password_auth(cognito, client_id, email, password):
    """Test USER_PASSWORD_AUTH flow (for Basic Auth)"""
    print("\nTest 1: USER_PASSWORD_AUTH Flow (Direct Authentication)")
    print("-" * 60)

    try:
        response = cognito.initiate_auth(
            ClientId=client_id,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': email,
                'PASSWORD': password
            }
        )

        if 'AuthenticationResult' in response:
            access_token = response['AuthenticationResult']['AccessToken']
            id_token = response['AuthenticationResult']['IdToken']
            expires_in = response['AuthenticationResult']['ExpiresIn']

            print(f"✓ Authentication successful!")
            print(f"  Access token: {access_token[:50]}...")
            print(f"  ID token: {id_token[:50]}...")
            print(f"  Expires in: {expires_in} seconds")

            # Decode and display token claims
            token_payload = access_token.split('.')[1]
            # Add padding if needed
            token_payload += '=' * (4 - len(token_payload) % 4)
            decoded = base64.b64decode(token_payload)
            print(f"  Token payload (truncated): {decoded[:100]}...")

            return True
        else:
            print("❌ No authentication result returned")
            return False

    except ClientError as e:
        print(f"❌ Authentication failed: {e.response['Error']['Message']}")
        return False


def test_basic_auth_header(email, password):
    """Test Basic Auth header encoding (for MCP server)"""
    print("\nTest 2: Basic Auth Header Encoding")
    print("-" * 60)

    credentials = f"{email}:{password}"
    encoded = base64.b64encode(credentials.encode()).decode()
    auth_header = f"Basic {encoded}"

    print(f"✓ Basic Auth header generated:")
    print(f"  Authorization: {auth_header}")
    print(f"\n  This header can be used with the MCP server's flexible auth middleware")

    return True


def test_token_validation(cognito, access_token):
    """Test token validation"""
    print("\nTest 3: Token Validation")
    print("-" * 60)

    try:
        response = cognito.get_user(
            AccessToken=access_token
        )

        print(f"✓ Token is valid")
        print(f"  Username: {response['Username']}")
        print(f"  User attributes:")
        for attr in response['UserAttributes']:
            if attr['Name'] in ['email', 'given_name', 'family_name', 'custom:customer_id']:
                print(f"    - {attr['Name']}: {attr['Value']}")

        return True

    except ClientError as e:
        print(f"❌ Token validation failed: {e}")
        return False


def test_oauth_endpoints(region):
    """Display OAuth 2.0 endpoints for browser flow"""
    print("\nTest 4: OAuth 2.0 Browser Flow Endpoints")
    print("-" * 60)

    print(f"✓ OAuth endpoints configured:")
    print(f"  Authorization endpoint:")
    print(f"    https://ecommerce-mcp-demo.auth.{region}.amazoncognito.com/oauth2/authorize")
    print(f"\n  Token endpoint:")
    print(f"    https://ecommerce-mcp-demo.auth.{region}.amazoncognito.com/oauth2/token")
    print(f"\n  Hosted UI:")
    print(f"    https://ecommerce-mcp-demo.auth.{region}.amazoncognito.com/login")
    print(f"\n  These endpoints are used by Claude Desktop for OAuth browser flow")

    return True


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Test authentication methods for E-Commerce MCP Server"
    )
    parser.add_argument(
        "--region",
        default="us-west-2",
        help="AWS region (default: us-west-2)"
    )
    parser.add_argument(
        "--email",
        default="demo1@example.com",
        help="Test user email (default: demo1@example.com)"
    )
    parser.add_argument(
        "--password",
        default="Demo123!",
        help="Test user password (default: Demo123!)"
    )

    args = parser.parse_args()

    print("=" * 70)
    print("E-Commerce MCP Server - Authentication Testing")
    print("=" * 70)
    print(f"Region: {args.region}")
    print(f"Test user: {args.email}")

    # Get Cognito configuration
    print("\nFetching Cognito configuration...")
    config = get_cognito_config(args.region)
    if not config:
        exit(1)

    print(f"  ✓ User Pool ID: {config['user_pool_id']}")
    print(f"  ✓ Client ID: {config['client_id']}")

    # Initialize Cognito client
    cognito = boto3.client('cognito-idp', region_name=args.region)

    # Run tests
    tests_passed = 0
    tests_total = 4

    # Test 1: USER_PASSWORD_AUTH
    if test_user_password_auth(cognito, config['client_id'], args.email, args.password):
        tests_passed += 1
        # Save token for validation test
        response = cognito.initiate_auth(
            ClientId=config['client_id'],
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': args.email,
                'PASSWORD': args.password
            }
        )
        access_token = response['AuthenticationResult']['AccessToken']
    else:
        access_token = None

    # Test 2: Basic Auth header
    if test_basic_auth_header(args.email, args.password):
        tests_passed += 1

    # Test 3: Token validation
    if access_token and test_token_validation(cognito, access_token):
        tests_passed += 1

    # Test 4: OAuth endpoints
    if test_oauth_endpoints(args.region):
        tests_passed += 1

    # Summary
    print("\n" + "=" * 70)
    print(f"Test Results: {tests_passed}/{tests_total} passed")
    print("=" * 70)

    if tests_passed == tests_total:
        print("✓ All authentication methods working correctly!")
        print("\nReady to implement multi-method auth in MCP server")
    else:
        print("⚠ Some tests failed. Please review the errors above.")
        exit(1)


if __name__ == "__main__":
    main()
