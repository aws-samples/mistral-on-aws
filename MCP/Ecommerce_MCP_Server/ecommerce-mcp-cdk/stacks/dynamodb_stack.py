"""
DynamoDB Stack for E-Commerce MCP Server

This stack creates 5 DynamoDB tables with 8 Global Secondary Indexes:
1. Products Table - no GSIs
2. Customers Table - 1 GSI (email-index)
3. Orders Table - 2 GSIs (customer_id-created_at-index, customer_id-product_id-index)
4. Reviews Table - 3 GSIs (product_id-created_at-index, product_id-rating-index, customer_id-created_at-index)
5. Returns Table - 2 GSIs (order_id-index, customer_id-created_at-index)
"""

from aws_cdk import (
    Stack,
    RemovalPolicy,
    CfnOutput,
    aws_dynamodb as dynamodb,
)
from constructs import Construct


class DynamoDBStack(Stack):
    """CDK Stack for DynamoDB tables"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ============================================================
        # TABLE 1: Products Table
        # ============================================================
        self.products_table = dynamodb.Table(
            self, "ProductsTable",
            table_name="ecommerce-products",
            partition_key=dynamodb.Attribute(
                name="product_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY  # Demo only - will delete data on stack deletion
            # Point-in-time recovery disabled for cost optimization (demo only)
        )

        # Attributes: name, description, price, image_urls, stock_quantity, category
        # No GSIs needed - primary key access only

        # ============================================================
        # TABLE 2: Customers Table
        # ============================================================
        self.customers_table = dynamodb.Table(
            self, "CustomersTable",
            table_name="ecommerce-customers",
            partition_key=dynamodb.Attribute(
                name="customer_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY
        )

        # GSI 1: email-index (for Cognito user lookup)
        self.customers_table.add_global_secondary_index(
            index_name="email-index",
            partition_key=dynamodb.Attribute(
                name="email",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )

        # Attributes: cognito_user_id, email, name, shipping_address, payment_methods

        # ============================================================
        # TABLE 3: Orders Table
        # ============================================================
        self.orders_table = dynamodb.Table(
            self, "OrdersTable",
            table_name="ecommerce-orders",
            partition_key=dynamodb.Attribute(
                name="order_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY
        )

        # GSI 1: customer_id-created_at-index (order history)
        self.orders_table.add_global_secondary_index(
            index_name="customer_id-created_at-index",
            partition_key=dynamodb.Attribute(
                name="customer_id",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="created_at",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )

        # GSI 2: customer_id-product_id-index (purchase validation for reviews)
        self.orders_table.add_global_secondary_index(
            index_name="customer_id-product_id-index",
            partition_key=dynamodb.Attribute(
                name="customer_id",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="product_id",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.KEYS_ONLY  # Optimization - only need keys for validation
        )

        # Attributes: customer_id, product_id, quantity, total_price, status, created_at, shipping_address, payment_method

        # ============================================================
        # TABLE 4: Reviews Table
        # ============================================================
        self.reviews_table = dynamodb.Table(
            self, "ReviewsTable",
            table_name="ecommerce-reviews",
            partition_key=dynamodb.Attribute(
                name="review_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY
        )

        # GSI 1: product_id-created_at-index (get product reviews sorted by recency)
        self.reviews_table.add_global_secondary_index(
            index_name="product_id-created_at-index",
            partition_key=dynamodb.Attribute(
                name="product_id",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="created_at",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )

        # GSI 2: product_id-rating-index (filter by rating)
        self.reviews_table.add_global_secondary_index(
            index_name="product_id-rating-index",
            partition_key=dynamodb.Attribute(
                name="product_id",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="rating",
                type=dynamodb.AttributeType.NUMBER
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )

        # GSI 3: customer_id-created_at-index (customer review history)
        self.reviews_table.add_global_secondary_index(
            index_name="customer_id-created_at-index",
            partition_key=dynamodb.Attribute(
                name="customer_id",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="created_at",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )

        # Attributes: product_id, customer_id, rating (1-5), review_text, title, created_at, verified_purchase

        # ============================================================
        # TABLE 5: Returns Table
        # ============================================================
        self.returns_table = dynamodb.Table(
            self, "ReturnsTable",
            table_name="ecommerce-returns",
            partition_key=dynamodb.Attribute(
                name="return_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY
        )

        # GSI 1: order_id-index (check existing returns for order)
        self.returns_table.add_global_secondary_index(
            index_name="order_id-index",
            partition_key=dynamodb.Attribute(
                name="order_id",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )

        # GSI 2: customer_id-created_at-index (return history)
        self.returns_table.add_global_secondary_index(
            index_name="customer_id-created_at-index",
            partition_key=dynamodb.Attribute(
                name="customer_id",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="created_at",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )

        # Attributes: order_id, customer_id, reason, status, created_at, processed_at

        # ============================================================
        # CloudFormation Outputs
        # ============================================================
        CfnOutput(self, "ProductsTableName",
                  value=self.products_table.table_name,
                  description="Products DynamoDB table name")

        CfnOutput(self, "CustomersTableName",
                  value=self.customers_table.table_name,
                  description="Customers DynamoDB table name")

        CfnOutput(self, "OrdersTableName",
                  value=self.orders_table.table_name,
                  description="Orders DynamoDB table name")

        CfnOutput(self, "ReviewsTableName",
                  value=self.reviews_table.table_name,
                  description="Reviews DynamoDB table name")

        CfnOutput(self, "ReturnsTableName",
                  value=self.returns_table.table_name,
                  description="Returns DynamoDB table name")

        CfnOutput(self, "ProductsTableArn",
                  value=self.products_table.table_arn,
                  description="Products table ARN")

        CfnOutput(self, "CustomersTableArn",
                  value=self.customers_table.table_arn,
                  description="Customers table ARN")

        CfnOutput(self, "OrdersTableArn",
                  value=self.orders_table.table_arn,
                  description="Orders table ARN")

        CfnOutput(self, "ReviewsTableArn",
                  value=self.reviews_table.table_arn,
                  description="Reviews table ARN")

        CfnOutput(self, "ReturnsTableArn",
                  value=self.returns_table.table_arn,
                  description="Returns table ARN")
