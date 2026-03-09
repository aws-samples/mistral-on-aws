#!/usr/bin/env python3
"""
Authentication and Runtime Testing Script for E-Commerce MCP Server

Tests OAuth 2.0 token acquisition and AgentCore Runtime invocation.

Usage:
    python test_auth_methods.py --runtime-arn <AgentCore Runtime ARN> \
        [--region us-west-2] [--email demo1@example.com]
"""

import argparse
import base64
import json
import urllib.parse
import uuid
import boto3
import requests
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
            print("Error: Missing Cognito configuration in stack outputs")
            return None

        return config

    except ClientError as e:
        print(f"Error getting Cognito configuration: {e}")
        return None


def get_access_token(cognito, client_id, email, password):
    """
    Obtain a Cognito access token via USER_PASSWORD_AUTH.
    Returns (access_token, success_bool).
    """
    print("\nStep 1: Obtain Cognito Access Token")
    print("-" * 60)

    try:
        response = cognito.initiate_auth(
            ClientId=client_id,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': email,
                'PASSWORD': password,
            },
        )

        if 'AuthenticationResult' not in response:
            print("No authentication result returned")
            return None, False

        access_token = response['AuthenticationResult']['AccessToken']
        expires_in = response['AuthenticationResult']['ExpiresIn']

        print(f"Authentication successful")
        print(f"  Access token: {access_token[:50]}...")
        print(f"  Expires in: {expires_in} seconds")

        return access_token, True

    except ClientError as e:
        print(f"Authentication failed: {e.response['Error']['Message']}")
        return None, False


def test_token_validation(cognito, access_token):
    """Validate the token and display user attributes."""
    print("\nStep 2: Validate Token / Inspect custom:customer_id")
    print("-" * 60)

    try:
        response = cognito.get_user(AccessToken=access_token)

        print(f"Token is valid")
        print(f"  Username: {response['Username']}")
        print(f"  User attributes:")
        for attr in response['UserAttributes']:
            if attr['Name'] in ['email', 'given_name', 'family_name', 'custom:customer_id']:
                print(f"    - {attr['Name']}: {attr['Value']}")

        return True

    except ClientError as e:
        print(f"Token validation failed: {e}")
        return False


def test_agentcore_runtime_invocation(runtime_arn, access_token, region):
    """
    Invoke the AgentCore Runtime with a tools/list MCP JSON-RPC request.

    Uses HTTPS + Bearer token: AgentCore validates the JWT at the edge, then
    forwards the Authorization header to the server (per requestHeaderAllowlist).
    Confirms the runtime is reachable, the JWT is accepted, and 6 tools are returned.
    """
    print("\nStep 3: Invoke AgentCore Runtime (tools/list)")
    print("-" * 60)

    dp_endpoint = f"https://bedrock-agentcore.{region}.amazonaws.com"
    escaped_arn = urllib.parse.quote(runtime_arn, safe="")
    url = f"{dp_endpoint}/runtimes/{escaped_arn}/invocations"
    session_id = str(uuid.uuid4())

    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream, application/json",
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
        "Authorization": f"Bearer {access_token}",
    }
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {},
    }

    try:
        response = requests.post(
            url,
            params={"qualifier": "DEFAULT"},
            headers=headers,
            json=body,
            timeout=60,
            stream=True,
        )

        print(f"  HTTP status: {response.status_code}")

        if response.status_code != 200:
            print(f"  Response: {response.text[:400]}")
            return False

        # Response is SSE: consume stream and find first data: line
        result = None
        for chunk in response.iter_lines():
            if isinstance(chunk, bytes):
                chunk = chunk.decode()
            if chunk.startswith("data:"):
                result = json.loads(chunk[5:].strip())
                break

        tools = result.get('result', {}).get('tools', []) if result else []
        tool_names = [t.get('name') for t in tools]

        print(f"  Runtime responded successfully")
        print(f"  Tools returned: {len(tools)}")
        for name in tool_names:
            print(f"    - {name}")

        expected = {
            'search_products', 'get_product_reviews',
            'order_product', 'write_product_review',
            'get_order_history', 'initiate_return',
        }
        if expected == set(tool_names):
            print("  All 6 expected tools present")
            return True
        else:
            missing = expected - set(tool_names)
            unexpected = set(tool_names) - expected
            if missing:
                print(f"  Missing tools: {missing}")
            if unexpected:
                print(f"  Unexpected tools: {unexpected}")
            return False

    except Exception as e:
        print(f"AgentCore invocation failed: {e}")
        return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Test AgentCore Runtime for E-Commerce MCP Server"
    )
    parser.add_argument(
        "--runtime-arn",
        required=True,
        help="AgentCore Runtime ARN (from `agentcore launch` output)",
    )
    parser.add_argument(
        "--region",
        default="us-west-2",
        help="AWS region (default: us-west-2)",
    )
    parser.add_argument(
        "--email",
        default="demo1@example.com",
        help="Test user email (default: demo1@example.com)",
    )
    parser.add_argument(
        "--password",
        default="Demo123!",
        help="Test user password (default: Demo123!)",
    )

    args = parser.parse_args()

    print("=" * 70)
    print("E-Commerce MCP Server - AgentCore Runtime Testing")
    print("=" * 70)
    print(f"Region:      {args.region}")
    print(f"Runtime ARN: {args.runtime_arn}")
    print(f"Test user:   {args.email}")

    # Get Cognito configuration
    print("\nFetching Cognito configuration...")
    config = get_cognito_config(args.region)
    if not config:
        exit(1)

    print(f"  User Pool ID: {config['user_pool_id']}")
    print(f"  Client ID:    {config['client_id']}")

    cognito = boto3.client('cognito-idp', region_name=args.region)

    tests_passed = 0
    tests_total = 3

    # Step 1: Obtain access token
    access_token, ok = get_access_token(cognito, config['client_id'], args.email, args.password)
    if ok:
        tests_passed += 1
    else:
        print("\nCannot continue without a valid access token.")
        exit(1)

    # Step 2: Validate token
    if test_token_validation(cognito, access_token):
        tests_passed += 1

    # Step 3: Invoke AgentCore Runtime
    if test_agentcore_runtime_invocation(args.runtime_arn, access_token, args.region):
        tests_passed += 1

    # Summary
    print("\n" + "=" * 70)
    print(f"Test Results: {tests_passed}/{tests_total} passed")
    print("=" * 70)

    if tests_passed == tests_total:
        print("All tests passed — AgentCore Runtime is operational.")
    else:
        print("Some tests failed. Review the errors above.")
        exit(1)


if __name__ == "__main__":
    main()
