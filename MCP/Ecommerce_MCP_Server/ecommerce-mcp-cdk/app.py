#!/usr/bin/env python3
"""
E-Commerce MCP Server CDK Application

This CDK app deploys the infrastructure for the E-Commerce MCP Server:
- DynamoDB tables (5 tables + 8 GSIs)
- AWS Cognito User Pool for authentication
- Data loader for synthetic data
"""

import aws_cdk as cdk
from stacks.dynamodb_stack import DynamoDBStack
from stacks.cognito_stack import CognitoStack
from stacks.data_loader_stack import DataLoaderStack

app = cdk.App()

# Get configuration from context or use defaults
region = app.node.try_get_context("region") or "us-west-2"
env = cdk.Environment(region=region)

# Stack 1: DynamoDB Tables
dynamodb_stack = DynamoDBStack(
    app,
    "EcommerceMcpDynamoDBStack",
    description="DynamoDB tables for E-Commerce MCP Server (5 tables + 8 GSIs)",
    env=env
)

# Stack 2: Cognito User Pool
cognito_stack = CognitoStack(
    app,
    "EcommerceMcpCognitoStack",
    description="Cognito User Pool and App Client for E-Commerce MCP Server authentication",
    env=env
)

# Stack 3: Data Loader (custom resource to load synthetic data)
data_loader_stack = DataLoaderStack(
    app,
    "EcommerceMcpDataLoaderStack",
    description="Custom resource to load synthetic data into DynamoDB tables",
    products_table=dynamodb_stack.products_table,
    customers_table=dynamodb_stack.customers_table,
    orders_table=dynamodb_stack.orders_table,
    reviews_table=dynamodb_stack.reviews_table,
    returns_table=dynamodb_stack.returns_table,
    env=env
)

# Add dependencies
data_loader_stack.add_dependency(dynamodb_stack)
data_loader_stack.add_dependency(cognito_stack)

# Add tags to all resources for cost tracking
cdk.Tags.of(app).add("Project", "EcommerceMcpServer")
cdk.Tags.of(app).add("Environment", "Demo")
cdk.Tags.of(app).add("ManagedBy", "CDK")

app.synth()
