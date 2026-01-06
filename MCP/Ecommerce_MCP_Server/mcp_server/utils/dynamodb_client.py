"""
DynamoDB Client for E-Commerce MCP Server

Provides convenient methods for interacting with DynamoDB tables.
Handles decimal conversion, error handling, and common query patterns.
"""

import os
from typing import List, Dict, Optional, Any
from decimal import Decimal
from datetime import datetime
import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError


class DynamoDBClient:
    """
    Wrapper for DynamoDB operations

    Provides methods for all 5 tables:
    - Products
    - Customers
    - Orders
    - Reviews
    - Returns
    """

    def __init__(self, region: Optional[str] = None):
        """
        Initialize DynamoDB client

        Args:
            region: AWS region (default: from AWS_REGION env var)
        """
        self.region = region or os.environ.get('AWS_REGION', 'us-west-2')
        self.dynamodb = boto3.resource('dynamodb', region_name=self.region)

        # Table references
        self.products_table = self.dynamodb.Table(
            os.environ.get('PRODUCTS_TABLE', 'ecommerce-products')
        )
        self.customers_table = self.dynamodb.Table(
            os.environ.get('CUSTOMERS_TABLE', 'ecommerce-customers')
        )
        self.orders_table = self.dynamodb.Table(
            os.environ.get('ORDERS_TABLE', 'ecommerce-orders')
        )
        self.reviews_table = self.dynamodb.Table(
            os.environ.get('REVIEWS_TABLE', 'ecommerce-reviews')
        )
        self.returns_table = self.dynamodb.Table(
            os.environ.get('RETURNS_TABLE', 'ecommerce-returns')
        )

    @staticmethod
    def decimal_to_float(obj: Any) -> Any:
        """Convert Decimal types to float for JSON serialization"""
        if isinstance(obj, list):
            return [DynamoDBClient.decimal_to_float(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: DynamoDBClient.decimal_to_float(v) for k, v in obj.items()}
        elif isinstance(obj, Decimal):
            return float(obj)
        else:
            return obj

    # ========================================================================
    # Products Table Methods
    # ========================================================================

    def get_product(self, product_id: str) -> Optional[Dict]:
        """Get product by ID"""
        try:
            response = self.products_table.get_item(Key={'product_id': product_id})
            return self.decimal_to_float(response.get('Item'))
        except ClientError as e:
            print(f"Error getting product: {e}")
            return None

    @staticmethod
    def _get_search_variants(query: str) -> List[str]:
        """Generate search variants to handle plurals and common variations."""
        query = query.lower().strip()
        variants = {query}

        # Handle plurals: remove common suffixes
        if query.endswith('ies'):
            variants.add(query[:-3] + 'y')  # batteries -> battery
        if query.endswith('es'):
            variants.add(query[:-2])  # watches -> watch
        if query.endswith('s') and len(query) > 2:
            variants.add(query[:-1])  # laptops -> laptop

        # Handle singular: add common plural forms
        if not query.endswith('s'):
            variants.add(query + 's')  # laptop -> laptops
        if query.endswith('y'):
            variants.add(query[:-1] + 'ies')  # battery -> batteries

        return list(variants)

    def search_products(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        Search products with filters

        Args:
            query: Search term (matches product name, case-insensitive, handles plurals)
            category: Filter by category
            min_price: Minimum price
            max_price: Maximum price
            limit: Maximum number of results

        Returns:
            List of matching products
        """
        try:
            # Build filter expression for non-query filters
            filter_expressions = []

            if category:
                filter_expressions.append(Attr('category').eq(category))

            if min_price is not None:
                filter_expressions.append(Attr('price').gte(Decimal(str(min_price))))

            if max_price is not None:
                filter_expressions.append(Attr('price').lte(Decimal(str(max_price))))

            # Scan with filters (acceptable for ~50 products)
            scan_kwargs = {}

            if filter_expressions:
                combined_filter = filter_expressions[0]
                for expr in filter_expressions[1:]:
                    combined_filter = combined_filter & expr
                scan_kwargs['FilterExpression'] = combined_filter

            response = self.products_table.scan(**scan_kwargs)
            items = self.decimal_to_float(response.get('Items', []))

            # Case-insensitive text search with plural handling
            if query:
                search_variants = self._get_search_variants(query)
                items = [
                    item for item in items
                    if any(
                        variant in item.get('name', '').lower()
                        or variant in item.get('description', '').lower()
                        for variant in search_variants
                    )
                ]

            return items[:limit]

        except ClientError as e:
            print(f"Error searching products: {e}")
            return []

    def update_product_stock(
        self,
        product_id: str,
        quantity_change: int
    ) -> bool:
        """
        Update product stock (atomic operation)

        Args:
            product_id: Product ID
            quantity_change: Change in quantity (negative for decrease)

        Returns:
            bool: True if successful
        """
        try:
            self.products_table.update_item(
                Key={'product_id': product_id},
                UpdateExpression='SET stock_quantity = stock_quantity + :change',
                ConditionExpression='stock_quantity >= :min_stock',
                ExpressionAttributeValues={
                    ':change': quantity_change,
                    ':min_stock': abs(quantity_change) if quantity_change < 0 else 0
                }
            )
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                print(f"Insufficient stock for product {product_id}")
            else:
                print(f"Error updating stock: {e}")
            return False

    # ========================================================================
    # Customers Table Methods
    # ========================================================================

    def get_customer(self, customer_id: str) -> Optional[Dict]:
        """Get customer by ID"""
        try:
            response = self.customers_table.get_item(Key={'customer_id': customer_id})
            return self.decimal_to_float(response.get('Item'))
        except ClientError as e:
            print(f"Error getting customer: {e}")
            return None

    def get_customer_by_email(self, email: str) -> Optional[Dict]:
        """Get customer by email (using GSI)"""
        try:
            response = self.customers_table.query(
                IndexName='email-index',
                KeyConditionExpression=Key('email').eq(email)
            )
            items = response.get('Items', [])
            return self.decimal_to_float(items[0]) if items else None
        except ClientError as e:
            print(f"Error getting customer by email: {e}")
            return None

    # ========================================================================
    # Orders Table Methods
    # ========================================================================

    def create_order(self, order_data: Dict) -> Optional[str]:
        """
        Create new order

        Args:
            order_data: Order details (must include order_id, customer_id, product_id, etc.)

        Returns:
            str: Order ID if successful, None otherwise
        """
        try:
            # Convert floats to Decimal
            order_data_decimal = {}
            for k, v in order_data.items():
                if isinstance(v, float):
                    order_data_decimal[k] = Decimal(str(v))
                else:
                    order_data_decimal[k] = v

            self.orders_table.put_item(Item=order_data_decimal)
            return order_data['order_id']
        except ClientError as e:
            print(f"Error creating order: {e}")
            return None

    def get_order(self, order_id: str) -> Optional[Dict]:
        """Get order by ID"""
        try:
            response = self.orders_table.get_item(Key={'order_id': order_id})
            return self.decimal_to_float(response.get('Item'))
        except ClientError as e:
            print(f"Error getting order: {e}")
            return None

    def get_customer_orders(
        self,
        customer_id: str,
        limit: int = 50
    ) -> List[Dict]:
        """Get orders for a customer (using GSI)"""
        try:
            response = self.orders_table.query(
                IndexName='customer_id-created_at-index',
                KeyConditionExpression=Key('customer_id').eq(customer_id),
                ScanIndexForward=False,  # Most recent first
                Limit=limit
            )
            return self.decimal_to_float(response.get('Items', []))
        except ClientError as e:
            print(f"Error getting customer orders: {e}")
            return []

    def check_customer_purchased_product(
        self,
        customer_id: str,
        product_id: str
    ) -> bool:
        """Check if customer has purchased a specific product (for review validation)"""
        try:
            response = self.orders_table.query(
                IndexName='customer_id-product_id-index',
                KeyConditionExpression=Key('customer_id').eq(customer_id) & Key('product_id').eq(product_id),
                Limit=1
            )
            return len(response.get('Items', [])) > 0
        except ClientError as e:
            print(f"Error checking purchase: {e}")
            return False

    # ========================================================================
    # Reviews Table Methods
    # ========================================================================

    def create_review(self, review_data: Dict) -> Optional[str]:
        """Create new review"""
        try:
            # Convert floats to Decimal
            review_data_decimal = {}
            for k, v in review_data.items():
                if isinstance(v, float):
                    review_data_decimal[k] = Decimal(str(v))
                else:
                    review_data_decimal[k] = v

            self.reviews_table.put_item(Item=review_data_decimal)
            return review_data['review_id']
        except ClientError as e:
            print(f"Error creating review: {e}")
            return None

    def get_product_reviews(
        self,
        product_id: str,
        filter_by_rating: Optional[int] = None,
        sort_by_recent: bool = True,
        limit: int = 3
    ) -> List[Dict]:
        """
        Get reviews for a product

        Args:
            product_id: Product ID
            filter_by_rating: Optional rating filter (1-5)
            sort_by_recent: If True, sort by most recent first
            limit: Maximum number of reviews (default: 3 for top reviews)

        Returns:
            List of reviews
        """
        try:
            if filter_by_rating:
                # Use product_id-rating-index
                response = self.reviews_table.query(
                    IndexName='product_id-rating-index',
                    KeyConditionExpression=Key('product_id').eq(product_id) & Key('rating').eq(filter_by_rating),
                    ScanIndexForward=False,
                    Limit=limit
                )
            else:
                # Use product_id-created_at-index
                response = self.reviews_table.query(
                    IndexName='product_id-created_at-index',
                    KeyConditionExpression=Key('product_id').eq(product_id),
                    ScanIndexForward=not sort_by_recent,
                    Limit=limit
                )

            return self.decimal_to_float(response.get('Items', []))
        except ClientError as e:
            print(f"Error getting reviews: {e}")
            return []

    # ========================================================================
    # Returns Table Methods
    # ========================================================================

    def create_return(self, return_data: Dict) -> Optional[str]:
        """Create new return request"""
        try:
            # Convert floats to Decimal
            return_data_decimal = {}
            for k, v in return_data.items():
                if isinstance(v, float):
                    return_data_decimal[k] = Decimal(str(v))
                else:
                    return_data_decimal[k] = v

            self.returns_table.put_item(Item=return_data_decimal)
            return return_data['return_id']
        except ClientError as e:
            print(f"Error creating return: {e}")
            return None

    def get_returns_for_order(self, order_id: str) -> List[Dict]:
        """Check if order already has a return request (using GSI)"""
        try:
            response = self.returns_table.query(
                IndexName='order_id-index',
                KeyConditionExpression=Key('order_id').eq(order_id)
            )
            return self.decimal_to_float(response.get('Items', []))
        except ClientError as e:
            print(f"Error getting returns: {e}")
            return []
