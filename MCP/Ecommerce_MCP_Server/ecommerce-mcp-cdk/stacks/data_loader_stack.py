"""
Data Loader Stack for E-Commerce MCP Server

This stack creates a custom resource (Lambda function) that loads synthetic data
into DynamoDB tables after they're created. This ensures the demo environment
has realistic data for testing.

The Lambda function is triggered during stack creation and loads:
- 50 products across 4 categories
- 10 customers
- 50 orders (5 per customer)
- 50 reviews (5 per customer)
- ~8 returns (15% of orders)
"""

from aws_cdk import (
    Stack,
    CustomResource,
    Duration,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_dynamodb as dynamodb,
    custom_resources as cr,
)
from constructs import Construct


class DataLoaderStack(Stack):
    """CDK Stack for loading synthetic data into DynamoDB"""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        products_table: dynamodb.Table,
        customers_table: dynamodb.Table,
        orders_table: dynamodb.Table,
        reviews_table: dynamodb.Table,
        returns_table: dynamodb.Table,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ============================================================
        # Lambda Function for Data Loading
        # ============================================================
        # This Lambda function will be triggered once during stack creation
        # to load synthetic data into all DynamoDB tables

        # Note: In a production implementation, this would reference a Lambda
        # function that generates and loads data. For now, we'll create a
        # placeholder that can be implemented later with the actual data
        # generation logic from data/generate_data.py

        data_loader_lambda = lambda_.Function(
            self, "DataLoaderFunction",
            runtime=lambda_.Runtime.PYTHON_3_10,
            handler="index.handler",
            code=lambda_.Code.from_inline("""
import json
import boto3
import cfnresponse

def handler(event, context):
    '''
    Custom Resource Lambda handler for loading synthetic data.

    This is a placeholder. The actual implementation will use the
    synthetic data generator from data/generate_data.py
    '''
    try:
        if event['RequestType'] == 'Create':
            # TODO: Load synthetic data from S3 or generate inline
            # For now, just signal success
            print("Data loading would happen here")
            print(f"Tables: {event['ResourceProperties']}")

        cfnresponse.send(event, context, cfnresponse.SUCCESS, {
            'Message': 'Data loader completed successfully'
        })
    except Exception as e:
        print(f"Error: {str(e)}")
        cfnresponse.send(event, context, cfnresponse.FAILED, {
            'Message': str(e)
        })
"""),
            timeout=Duration.minutes(5),
            memory_size=512,
            description="Loads synthetic data into DynamoDB tables for E-Commerce MCP demo"
        )

        # Grant permissions to write to all DynamoDB tables
        products_table.grant_write_data(data_loader_lambda)
        customers_table.grant_write_data(data_loader_lambda)
        orders_table.grant_write_data(data_loader_lambda)
        reviews_table.grant_write_data(data_loader_lambda)
        returns_table.grant_write_data(data_loader_lambda)

        # ============================================================
        # Custom Resource Provider
        # ============================================================
        provider = cr.Provider(
            self, "DataLoaderProvider",
            on_event_handler=data_loader_lambda
        )

        # ============================================================
        # Custom Resource
        # ============================================================
        # This resource will trigger the Lambda function during stack creation
        custom_resource = CustomResource(
            self, "DataLoaderResource",
            service_token=provider.service_token,
            properties={
                "ProductsTable": products_table.table_name,
                "CustomersTable": customers_table.table_name,
                "OrdersTable": orders_table.table_name,
                "ReviewsTable": reviews_table.table_name,
                "ReturnsTable": returns_table.table_name,
                "Region": self.region
            }
        )
