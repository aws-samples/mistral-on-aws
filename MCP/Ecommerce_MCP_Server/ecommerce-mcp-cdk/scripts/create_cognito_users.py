#!/usr/bin/env python3
"""
Cognito User Setup Script for E-Commerce MCP Server

Creates Cognito users from synthetic customer data and links them
with DynamoDB customer records via custom attribute 'customer_id'.

All demo users will have the password: Demo123!

Usage:
    python create_cognito_users.py [--region us-west-2] [--user-pool-id <id>]
"""

import json
import argparse
import boto3
from botocore.exceptions import ClientError


def get_user_pool_id(region):
    """Get User Pool ID from CloudFormation stack outputs"""
    cfn = boto3.client('cloudformation', region_name=region)

    try:
        response = cfn.describe_stacks(StackName='EcommerceMcpCognitoStack')
        outputs = response['Stacks'][0]['Outputs']

        for output in outputs:
            if output['OutputKey'] == 'UserPoolId':
                return output['OutputValue']

        print("❌ Error: UserPoolId not found in stack outputs")
        return None

    except ClientError as e:
        if e.response['Error']['Code'] == 'ValidationError':
            print("❌ Error: EcommerceMcpCognitoStack not found")
            print("Please deploy the CDK stack first: cdk deploy --all")
        else:
            print(f"❌ Error getting stack outputs: {e}")
        return None


def create_cognito_user(cognito, user_pool_id, customer):
    """
    Create a Cognito user and set custom attributes

    Args:
        cognito: boto3 Cognito IDP client
        user_pool_id: Cognito User Pool ID
        customer: Customer data from synthetic_data.json
    """
    email = customer['email']
    customer_id = customer['customer_id']

    try:
        # Create user with temporary password
        response = cognito.admin_create_user(
            UserPoolId=user_pool_id,
            Username=email,
            UserAttributes=[
                {'Name': 'email', 'Value': email},
                {'Name': 'email_verified', 'Value': 'true'},
                {'Name': 'given_name', 'Value': customer['given_name']},
                {'Name': 'family_name', 'Value': customer['family_name']},
                {'Name': 'custom:customer_id', 'Value': customer_id}
            ],
            TemporaryPassword='TempPass123!',
            MessageAction='SUPPRESS'  # Don't send welcome email
        )

        # Set permanent password (Demo123!)
        cognito.admin_set_user_password(
            UserPoolId=user_pool_id,
            Username=email,
            Password='Demo123!',
            Permanent=True
        )

        cognito_user_id = response['User']['Username']
        print(f"  ✓ Created user: {email} (customer_id: {customer_id})")

        return cognito_user_id

    except ClientError as e:
        if e.response['Error']['Code'] == 'UsernameExistsException':
            print(f"  ⚠ User already exists: {email}")
            # Get existing user's sub
            try:
                user = cognito.admin_get_user(
                    UserPoolId=user_pool_id,
                    Username=email
                )
                for attr in user['UserAttributes']:
                    if attr['Name'] == 'sub':
                        return attr['Value']
            except:
                return None
        else:
            print(f"  ❌ Error creating user {email}: {e}")
            return None


def update_customer_record(dynamodb, customer_id, cognito_user_id, region):
    """Update DynamoDB customer record with Cognito user ID"""
    table = dynamodb.Table('ecommerce-customers')

    try:
        table.update_item(
            Key={'customer_id': customer_id},
            UpdateExpression='SET cognito_user_id = :cognito_id',
            ExpressionAttributeValues={':cognito_id': cognito_user_id}
        )
        return True
    except ClientError as e:
        print(f"  ❌ Error updating customer record: {e}")
        return False


def setup_cognito_users(region, user_pool_id=None, data_file="../data/synthetic_data.json"):
    """Create all Cognito users from synthetic data"""
    print(f"E-Commerce MCP Server - Cognito User Setup")
    print(f"Region: {region}")
    print(f"Data file: {data_file}\n")

    # Get User Pool ID from CloudFormation if not provided
    if not user_pool_id:
        print("Getting User Pool ID from CloudFormation...")
        user_pool_id = get_user_pool_id(region)
        if not user_pool_id:
            return False
        print(f"  ✓ User Pool ID: {user_pool_id}\n")

    # Initialize AWS clients
    cognito = boto3.client('cognito-idp', region_name=region)
    dynamodb = boto3.resource('dynamodb', region_name=region)

    # Load customer data
    print(f"Loading customer data from {data_file}...")
    try:
        with open(data_file, 'r') as f:
            data = json.load(f)
            customers = data['customers']
    except FileNotFoundError:
        print(f"❌ Error: File '{data_file}' not found")
        print("Please run 'python generate_data.py' first")
        return False

    print(f"  ✓ Loaded {len(customers)} customers\n")

    # Create Cognito users
    print("Creating Cognito users...")
    created_count = 0
    updated_count = 0

    for customer in customers:
        cognito_user_id = create_cognito_user(cognito, user_pool_id, customer)

        if cognito_user_id:
            # Update DynamoDB customer record
            if update_customer_record(dynamodb, customer['customer_id'], cognito_user_id, region):
                updated_count += 1
            created_count += 1

    print(f"\n✓ Created {created_count} Cognito users")
    print(f"✓ Updated {updated_count} DynamoDB customer records")

    return True


def verify_setup(region, user_pool_id):
    """Verify Cognito users were created correctly"""
    print("\nVerifying Cognito setup...")

    cognito = boto3.client('cognito-idp', region_name=region)

    try:
        # List users
        response = cognito.list_users(UserPoolId=user_pool_id)
        users = response['Users']

        print(f"  ✓ Found {len(users)} users in Cognito User Pool")

        # Check a sample user
        if users:
            sample_user = users[0]
            print(f"\n  Sample user attributes:")
            for attr in sample_user['Attributes']:
                if attr['Name'] in ['email', 'given_name', 'family_name', 'custom:customer_id']:
                    print(f"    - {attr['Name']}: {attr['Value']}")

        # Test Hosted UI URL
        print(f"\n  Cognito Hosted UI:")
        print(f"    https://ecommerce-mcp-demo.auth.{region}.amazoncognito.com/login")

        return True

    except ClientError as e:
        print(f"  ❌ Error verifying setup: {e}")
        return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Create Cognito users for E-Commerce MCP Server"
    )
    parser.add_argument(
        "--region",
        default="us-west-2",
        help="AWS region (default: us-west-2)"
    )
    parser.add_argument(
        "--user-pool-id",
        help="Cognito User Pool ID (optional, will fetch from CloudFormation)"
    )
    parser.add_argument(
        "--data-file",
        default="../data/synthetic_data.json",
        help="Path to synthetic data JSON file"
    )

    args = parser.parse_args()

    success = setup_cognito_users(args.region, args.user_pool_id, args.data_file)

    if success and args.user_pool_id:
        verify_setup(args.region, args.user_pool_id)

    if success:
        print("\n" + "=" * 70)
        print("Demo User Credentials:")
        print("=" * 70)
        print("Email: demo1@example.com through demo10@example.com")
        print("Password: Demo123!")
        print("\nThese credentials work for all authentication methods:")
        print("  1. OAuth browser flow (Claude Desktop)")
        print("  2. Basic Auth (Mistral AI Studio)")
        print("  3. Direct /auth/login endpoint (Strands Agents)")
        print("=" * 70)
    else:
        exit(1)


if __name__ == "__main__":
    main()
