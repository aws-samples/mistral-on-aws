#!/usr/bin/env python3
"""
E-Commerce MCP Server - Streamable HTTP Transport

A Model Context Protocol (MCP) server for e-commerce operations using
streamable HTTP transport. Designed for AI agents like Strands Agents
and Mistral AI Studio.

Features:
- 6 MCP tools for e-commerce operations
- AWS Cognito authentication (Bearer token or Basic auth)
- DynamoDB backend for data persistence
- Streamable HTTP transport for native MCP protocol

Authentication:
    Supports Bearer token and Basic auth via Authorization header.
    - Bearer <token>: Cognito JWT access token (get via /auth/login)
    - Basic <base64>: Base64-encoded email:password

Connect with Strands Agent:
    from mcp.client.streamable_http import streamablehttp_client
    from strands.tools.mcp import MCPClient

    mcp_client = MCPClient(
        lambda: streamablehttp_client(
            url="http://host:8000/mcp",
            headers={"Authorization": f"Bearer {token}"}
        )
    )

Environment Variables:
- PORT: Server port (default: 8000)
- AWS_REGION: AWS region (default: us-west-2)
- COGNITO_USER_POOL_ID: Cognito User Pool ID
- COGNITO_CLIENT_ID: Cognito App Client ID
- PRODUCTS_TABLE: DynamoDB products table name
- CUSTOMERS_TABLE: DynamoDB customers table name
- ORDERS_TABLE: DynamoDB orders table name
- REVIEWS_TABLE: DynamoDB reviews table name
- RETURNS_TABLE: DynamoDB returns table name
"""

import os
import sys
import contextvars
from datetime import datetime, timedelta
from typing import Optional
import uuid

from fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.dynamodb_client import DynamoDBClient
from utils.auth import authenticate_request, CognitoAuthenticator, AuthenticationError


# ============================================================================
# Configuration
# ============================================================================

PORT = int(os.environ.get('PORT', 8000))
AWS_REGION = os.environ.get('AWS_REGION', 'us-west-2')


# ============================================================================
# Context Variables for User Authentication
# ============================================================================

current_user_context = contextvars.ContextVar('current_user_context', default=None)


def get_current_customer_id() -> str:
    """Get the customer_id for the current request."""
    user_ctx = current_user_context.get()
    if user_ctx and 'customer_id' in user_ctx:
        return user_ctx['customer_id']
    return 'anonymous'


# ============================================================================
# Initialize MCP Server and Database
# ============================================================================

mcp = FastMCP("ecommerce-mcp-server")
db = DynamoDBClient()


# ============================================================================
# Authentication Middleware
# ============================================================================

class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Middleware to authenticate requests and set user context."""

    async def dispatch(self, request: Request, call_next):
        auth_header = request.headers.get('Authorization')

        if auth_header:
            try:
                user_context = await authenticate_request(auth_header)
                token = current_user_context.set(user_context)
                try:
                    response = await call_next(request)
                finally:
                    current_user_context.reset(token)
                return response
            except AuthenticationError as e:
                # Allow anonymous access for public tools
                pass

        response = await call_next(request)
        return response


# ============================================================================
# Auth Login Endpoint
# ============================================================================

async def auth_login(request: Request) -> JSONResponse:
    """
    POST /auth/login - Get access token with email/password

    Request body: {"email": "user@example.com", "password": "password"}
    Response: {"access_token": "...", "token_type": "Bearer", "expires_in": 3600, "customer_id": "..."}
    """
    try:
        body = await request.json()
        email = body.get('email')
        password = body.get('password')

        if not email or not password:
            return JSONResponse(
                {"error": "Missing email or password"},
                status_code=400
            )

        user_pool_id = os.environ.get('COGNITO_USER_POOL_ID')
        client_id = os.environ.get('COGNITO_CLIENT_ID')

        if not user_pool_id or not client_id:
            return JSONResponse(
                {"error": "Authentication not configured"},
                status_code=500
            )

        authenticator = CognitoAuthenticator(AWS_REGION, user_pool_id, client_id)
        result = await authenticator.authenticate_with_password(email, password)

        return JSONResponse({
            "access_token": result['access_token'],
            "token_type": "Bearer",
            "expires_in": result['expires_in'],
            "customer_id": result['user_context']['customer_id']
        })

    except AuthenticationError as e:
        return JSONResponse({"error": str(e)}, status_code=401)
    except Exception as e:
        return JSONResponse({"error": f"Login failed: {str(e)}"}, status_code=500)


async def health_check(request: Request) -> JSONResponse:
    """GET /health - Health check endpoint"""
    return JSONResponse({
        "status": "healthy",
        "service": "ecommerce-mcp-server",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    })


# ============================================================================
# MCP Tools - E-Commerce Operations
# ============================================================================

@mcp.tool()
def search_products(
    query: str = "",
    category: str = None,
    min_price: float = None,
    max_price: float = None,
    limit: int = 10
) -> dict:
    """
    Search for products in the e-commerce catalog.

    PUBLIC - No authentication required.

    Args:
        query: Search keywords (e.g., "laptop", "wireless headphones")
        category: Filter by category (e.g., "Electronics", "Clothing")
        min_price: Minimum price in dollars
        max_price: Maximum price in dollars
        limit: Maximum number of results (default: 10)

    Returns:
        Dictionary with 'success', 'count', and 'products' list
    """
    try:
        products = db.search_products(
            query=query,
            category=category,
            min_price=min_price,
            max_price=max_price,
            limit=limit
        )
        return {"success": True, "count": len(products), "products": products}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def get_product_reviews(product_id: str, limit: int = 5) -> dict:
    """
    Get reviews for a specific product.

    PUBLIC - No authentication required.

    Args:
        product_id: The product ID to get reviews for
        limit: Maximum number of reviews to return

    Returns:
        Dictionary with product info and reviews list
    """
    try:
        reviews = db.get_product_reviews(product_id, limit=limit)
        product = db.get_product(product_id)
        return {
            "success": True,
            "product_name": product.get("name", "Unknown") if product else "Unknown",
            "review_count": len(reviews),
            "reviews": reviews
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def order_product(product_id: str, quantity: int = 1) -> dict:
    """
    Place an order for a product.

    REQUIRES AUTHENTICATION - Pass Authorization header.

    Args:
        product_id: The product ID to order
        quantity: Number of items to order (default: 1)

    Returns:
        Order confirmation with order_id, total, and delivery estimate
    """
    customer_id = get_current_customer_id()
    if customer_id == 'anonymous':
        return {"success": False, "error": "Authentication required"}

    try:
        product = db.get_product(product_id)
        if not product:
            return {"success": False, "error": "Product not found"}

        order_id = f"ord-{uuid.uuid4().hex[:10]}"
        price = float(product.get("price", 0))
        total = price * quantity

        order = {
            "order_id": order_id,
            "customer_id": customer_id,
            "product_id": product_id,
            "product_name": product.get("name"),
            "quantity": quantity,
            "unit_price": price,
            "total_price": total,
            "status": "placed",
            "created_at": datetime.now().isoformat(),
            "estimated_delivery": (datetime.now() + timedelta(days=3)).isoformat()
        }

        db.create_order(order)

        return {
            "success": True,
            "order_id": order_id,
            "product_name": product.get("name"),
            "quantity": quantity,
            "total_price": total,
            "status": "placed",
            "estimated_delivery": order["estimated_delivery"]
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def write_product_review(product_id: str, rating: int, review_text: str) -> dict:
    """
    Write a review for a product.

    REQUIRES AUTHENTICATION - Pass Authorization header.

    Args:
        product_id: The product ID to review
        rating: Star rating from 1 to 5
        review_text: Your review content

    Returns:
        Review confirmation with review_id
    """
    customer_id = get_current_customer_id()
    if customer_id == 'anonymous':
        return {"success": False, "error": "Authentication required"}

    if not 1 <= rating <= 5:
        return {"success": False, "error": "Rating must be between 1 and 5"}

    try:
        product = db.get_product(product_id)
        if not product:
            return {"success": False, "error": "Product not found"}

        review_id = f"rev-{uuid.uuid4().hex[:10]}"
        review = {
            "review_id": review_id,
            "product_id": product_id,
            "customer_id": customer_id,
            "rating": rating,
            "review_text": review_text,
            "created_at": datetime.now().isoformat()
        }

        db.create_review(review)

        return {
            "success": True,
            "review_id": review_id,
            "product_name": product.get("name"),
            "rating": rating,
            "message": "Review submitted successfully"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def get_order_history(limit: int = 10) -> dict:
    """
    Get order history for the authenticated user.

    REQUIRES AUTHENTICATION - Pass Authorization header.

    Args:
        limit: Maximum number of orders to return

    Returns:
        List of past orders with status, product details, and pricing
    """
    customer_id = get_current_customer_id()
    if customer_id == 'anonymous':
        return {"success": False, "error": "Authentication required"}

    try:
        orders = db.get_customer_orders(customer_id, limit=limit)

        # Enrich orders with product names
        enriched_orders = []
        for order in orders:
            product_id = order.get('product_id')
            if product_id:
                product = db.get_product(product_id)
                if product:
                    order['product_name'] = product.get('name', 'Unknown Product')
                    order['product_category'] = product.get('category', 'Unknown')
                else:
                    order['product_name'] = 'Product Not Found'
            enriched_orders.append(order)

        return {"success": True, "order_count": len(enriched_orders), "orders": enriched_orders}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def initiate_return(order_id: str, reason: str) -> dict:
    """
    Initiate a return for an order.

    REQUIRES AUTHENTICATION - Pass Authorization header.

    Args:
        order_id: The order ID to return
        reason: Reason for the return

    Returns:
        Return confirmation with return_id and status
    """
    customer_id = get_current_customer_id()
    if customer_id == 'anonymous':
        return {"success": False, "error": "Authentication required"}

    try:
        order = db.get_order(order_id)
        if not order:
            return {"success": False, "error": "Order not found"}

        if order.get('customer_id') != customer_id:
            return {"success": False, "error": "Order does not belong to this customer"}

        existing_return = db.get_return_by_order(order_id)
        if existing_return:
            return {
                "success": False,
                "message": "Return already exists",
                "return_id": existing_return.get("return_id"),
                "status": existing_return.get("status")
            }

        return_id = f"ret-{uuid.uuid4().hex[:10]}"
        return_request = {
            "return_id": return_id,
            "order_id": order_id,
            "customer_id": customer_id,
            "reason": reason,
            "status": "requested",
            "created_at": datetime.now().isoformat()
        }

        db.create_return(return_request)

        return {
            "success": True,
            "return_id": return_id,
            "order_id": order_id,
            "status": "requested",
            "message": "Return request submitted"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("E-Commerce MCP Server")
    print("=" * 70)
    print(f"Port: {PORT}")
    print(f"Region: {AWS_REGION}")
    print()
    print("Endpoints:")
    print("  GET  /health      - Health check")
    print("  POST /auth/login  - Get access token")
    print("  *    /mcp         - MCP protocol (streamable HTTP)")
    print()
    print("MCP Tools:")
    print("  PUBLIC:")
    print("    - search_products")
    print("    - get_product_reviews")
    print("  AUTHENTICATED:")
    print("    - order_product")
    print("    - write_product_review")
    print("    - get_order_history")
    print("    - initiate_return")
    print()
    print("Authentication:")
    print("  1. Bearer token: Authorization: Bearer <token>")
    print("  2. Basic auth:   Authorization: Basic <base64(email:password)>")
    print("=" * 70)

    from starlette.applications import Starlette
    from starlette.routing import Route

    # Get MCP ASGI app configured for /mcp path
    mcp_app = mcp.http_app(path="/mcp")

    # Add custom routes to the MCP app's router
    custom_routes = [
        Route("/health", health_check, methods=["GET"]),
        Route("/auth/login", auth_login, methods=["POST"]),
    ]

    # Insert custom routes at the beginning
    mcp_app.router.routes = custom_routes + list(mcp_app.router.routes)

    # Add authentication middleware
    mcp_app.add_middleware(AuthenticationMiddleware)

    # Run server
    import uvicorn
    uvicorn.run(mcp_app, host="0.0.0.0", port=PORT)
