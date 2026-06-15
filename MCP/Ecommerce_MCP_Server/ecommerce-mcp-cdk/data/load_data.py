#!/usr/bin/env python3
"""
Data Loader for E-Commerce MCP Server

Loads synthetic data from synthetic_data.json into DynamoDB tables.
Requires AWS credentials to be configured (AWS CLI or environment variables).

Usage:
    python load_data.py [--region us-west-2]
"""

import json
import argparse
import boto3
from decimal import Decimal
from botocore.exceptions import ClientError


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder for Decimal types"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)


def convert_floats_to_decimal(obj):
    """Convert floats to Decimal for DynamoDB compatibility"""
    if isinstance(obj, list):
        return [convert_floats_to_decimal(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, float):
        return Decimal(str(obj))
    else:
        return obj


def batch_write_items(dynamodb, table_name, items, batch_size=25):
    """
    Write items to DynamoDB in batches

    Args:
        dynamodb: boto3 DynamoDB resource
        table_name: Name of the DynamoDB table
        items: List of items to write
        batch_size: Number of items per batch (max 25)
    """
    table = dynamodb.Table(table_name)
    total_items = len(items)
    written = 0

    print(f"  Writing {total_items} items to {table_name}...")

    for i in range(0, total_items, batch_size):
        batch = items[i:i + batch_size]

        with table.batch_writer() as writer:
            for item in batch:
                # Convert floats to Decimal for DynamoDB
                item_converted = convert_floats_to_decimal(item)
                writer.put_item(Item=item_converted)

        written += len(batch)
        print(f"    Progress: {written}/{total_items} items")

    print(f"  ✓ Loaded {total_items} items into {table_name}")


def verify_tables_exist(dynamodb, table_names):
    """Verify all required tables exist"""
    print("Verifying DynamoDB tables exist...")

    try:
        for table_name in table_names:
            table = dynamodb.Table(table_name)
            table.load()  # This will raise exception if table doesn't exist
            print(f"  ✓ Found table: {table_name}")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print(f"\n❌ Error: Table '{table_name}' not found")
            print("Please deploy the CDK stack first: cdk deploy --all")
            return False
        else:
            raise
    return True


def load_data(region, data_file="synthetic_data.json"):
    """Load synthetic data into DynamoDB"""
    print(f"E-Commerce MCP Server - Data Loader")
    print(f"Region: {region}")
    print(f"Data file: {data_file}\n")

    # Initialize DynamoDB client
    dynamodb = boto3.resource('dynamodb', region_name=region)

    # Table names
    table_names = {
        "products": "ecommerce-products",
        "customers": "ecommerce-customers",
        "orders": "ecommerce-orders",
        "reviews": "ecommerce-reviews",
        "returns": "ecommerce-returns"
    }

    # Verify tables exist
    if not verify_tables_exist(dynamodb, table_names.values()):
        return False

    # Load synthetic data
    print(f"\nLoading data from {data_file}...")
    try:
        with open(data_file, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: File '{data_file}' not found")
        print("Please run 'python generate_data.py' first")
        return False

    print(f"  ✓ Loaded data file")
    print(f"    Products: {len(data['products'])}")
    print(f"    Customers: {len(data['customers'])}")
    print(f"    Orders: {len(data['orders'])}")
    print(f"    Reviews: {len(data['reviews'])}")
    print(f"    Returns: {len(data['returns'])}")

    # Load data into tables
    print("\nLoading data into DynamoDB tables...")

    try:
        # Load products
        batch_write_items(dynamodb, table_names["products"], data["products"])

        # Load customers
        batch_write_items(dynamodb, table_names["customers"], data["customers"])

        # Load orders
        batch_write_items(dynamodb, table_names["orders"], data["orders"])

        # Load reviews
        batch_write_items(dynamodb, table_names["reviews"], data["reviews"])

        # Load returns
        batch_write_items(dynamodb, table_names["returns"], data["returns"])

        print("\n✓ All data loaded successfully!")
        return True

    except ClientError as e:
        print(f"\n❌ Error loading data: {e}")
        return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Load synthetic data into DynamoDB for E-Commerce MCP Server"
    )
    parser.add_argument(
        "--region",
        default="us-west-2",
        help="AWS region (default: us-west-2)"
    )
    parser.add_argument(
        "--data-file",
        default="synthetic_data.json",
        help="Path to synthetic data JSON file (default: synthetic_data.json)"
    )

    args = parser.parse_args()

    success = load_data(args.region, args.data_file)

    if success:
        print("\n" + "=" * 70)
        print("Next Steps:")
        print("=" * 70)
        print("1. Create Cognito users:")
        print("   python ../scripts/create_cognito_users.py")
        print("\n2. Test authentication:")
        print("   python ../scripts/test_auth_methods.py")
        print("\n3. Deploy MCP server to AgentCore Runtime")
        print("=" * 70)
    else:
        exit(1)


if __name__ == "__main__":
    main()
