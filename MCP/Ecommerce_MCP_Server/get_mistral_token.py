#!/usr/bin/env python3
"""
Generate a Cognito Bearer token for the Mistral AI Studio MCP connector.

All account-specific values (Client ID, Runtime ARN) are read at runtime
from SSM Parameter Store and agentcore status — nothing is hardcoded.

Usage:
    python get_mistral_token.py                        # uses demo1@example.com
    python get_mistral_token.py --user demo3           # demo3@example.com
    python get_mistral_token.py --email you@company.com --password MyPass1
    python get_mistral_token.py --region eu-west-1     # non-default region

The token is printed to stdout AND saved to mistral_token.txt (gitignored).

Paste the token into:
    Mistral AI Studio → Connectors → (your connector) → Edit → Header value
"""

import argparse
import urllib.parse
import boto3
from botocore.exceptions import ClientError
from datetime import datetime, timezone, timedelta
from pathlib import Path

OUTPUT_FILE  = Path(__file__).parent / "mistral_token.txt"
DEMO_USERS   = {f"demo{i}": f"demo{i}@example.com" for i in range(1, 11)}
DEFAULT_PASSWORD = "Demo123!"
SSM_CLIENT_ID    = "/ecommerce-mcp/cognito-client-id"
SSM_RUNTIME_ARN  = "/ecommerce-mcp/agentcore-runtime-arn"   # written by agentcore deploy


def get_ssm(name: str, region: str) -> str:
    """Read a value from SSM Parameter Store."""
    ssm = boto3.client("ssm", region_name=region)
    try:
        return ssm.get_parameter(Name=name)["Parameter"]["Value"]
    except ClientError as e:
        raise SystemExit(f"SSM parameter '{name}' not found: {e.response['Error']['Message']}\n"
                         f"Have you run 'cdk deploy --all' and 'agentcore deploy'?")


def get_runtime_arn(region: str) -> str:
    """
    Derive the AgentCore Runtime ARN.
    Tries SSM first; falls back to agentcore status parsing.
    """
    try:
        return get_ssm(SSM_RUNTIME_ARN, region)
    except SystemExit:
        pass

    # Fallback: parse from agentcore status output
    import subprocess, re
    result = subprocess.run(["agentcore", "status"], capture_output=True, text=True)
    match = re.search(r"arn:aws:bedrock-agentcore:[^\s]+", result.stdout)
    if match:
        return match.group(0)

    raise SystemExit(
        "Could not determine Runtime ARN.\n"
        "Run 'agentcore status' to confirm the runtime is deployed, then\n"
        "store the ARN in SSM:\n"
        f"  aws ssm put-parameter --name {SSM_RUNTIME_ARN} \\\n"
        "    --value <ARN> --type String --overwrite"
    )


def build_endpoint_url(runtime_arn: str, region: str) -> str:
    return (
        f"https://bedrock-agentcore.{region}.amazonaws.com"
        f"/runtimes/{urllib.parse.quote(runtime_arn, safe='')}/invocations"
    )


def get_token(email: str, password: str, client_id: str, region: str) -> dict:
    cognito = boto3.client("cognito-idp", region_name=region)
    try:
        resp = cognito.initiate_auth(
            ClientId=client_id,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": email, "PASSWORD": password},
        )
    except ClientError as e:
        code = e.response["Error"]["Code"]
        msg  = e.response["Error"]["Message"]
        raise SystemExit(f"Authentication failed ({code}): {msg}")

    auth = resp["AuthenticationResult"]
    return {
        "access_token": auth["AccessToken"],
        "expires_in":   auth["ExpiresIn"],
        "token_type":   auth["TokenType"],
    }


def main():
    parser = argparse.ArgumentParser(
        description="Get a Cognito Bearer token for Mistral AI Studio"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--user", metavar="DEMO_NUM",
                       help="Demo user shorthand: demo1 … demo10 (default: demo1)")
    group.add_argument("--email", metavar="EMAIL", help="Full email address")
    parser.add_argument("--password", metavar="PASSWORD",
                        help=f"Password (default: {DEFAULT_PASSWORD})")
    parser.add_argument("--region", default="us-west-2", metavar="REGION",
                        help="AWS region (default: us-west-2)")
    args = parser.parse_args()

    # Resolve email
    if args.email:
        email = args.email
    else:
        key = args.user or "demo1"
        if key not in DEMO_USERS:
            raise SystemExit(f"Unknown user '{key}'. Choose from: {', '.join(DEMO_USERS)}")
        email = DEMO_USERS[key]

    password = args.password or DEFAULT_PASSWORD

    # Resolve account-specific values from SSM / agentcore
    print("Reading configuration from SSM ...")
    client_id   = get_ssm(SSM_CLIENT_ID, args.region)
    runtime_arn = get_runtime_arn(args.region)
    endpoint    = build_endpoint_url(runtime_arn, args.region)

    # Get token
    print(f"Authenticating as {email} ...")
    result     = get_token(email, password, client_id, args.region)
    token      = result["access_token"]
    expires_in = result["expires_in"]
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    # Save to file (gitignored)
    OUTPUT_FILE.write_text(token)

    print()
    print("=" * 72)
    print("Token generated successfully")
    print(f"  User      : {email}")
    print(f"  Client ID : {client_id}  (from SSM {SSM_CLIENT_ID})")
    print(f"  Expires   : {expires_at.strftime('%Y-%m-%d %H:%M UTC')}  ({expires_in // 3600}h)")
    print(f"  Saved to  : {OUTPUT_FILE}")
    print("=" * 72)
    print()
    print("Paste into Mistral AI Studio → Connector → Edit → Header value:")
    print()
    print(token)
    print()
    print("=" * 72)
    print("Connector Server URL (from agentcore status):")
    print()
    print(endpoint)
    print()
    print("Header name : Authorization")
    print("Header type : Bearer")
    print("=" * 72)


if __name__ == "__main__":
    main()
