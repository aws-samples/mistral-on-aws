"""
Authentication utilities for E-Commerce MCP Server.

Token signature validation is handled by Amazon Bedrock AgentCore Runtime.
This module only reads user attributes from a pre-validated token.

Two token types are supported:
- USER_PASSWORD_AUTH tokens  — include 'aws.cognito.signin.user.admin' scope,
                               so cognito.get_user(AccessToken=...) works directly.
- OAuth 2.1 Authorization Code tokens — include only OIDC scopes (openid/email/
                               profile/phone), so get_user() fails. We fall back
                               to AdminGetUser() using the server's IAM role,
                               deriving the User Pool ID from the JWT 'iss' claim.

Performance Optimization:
- Token-based caching to avoid repeated Cognito API calls
- Cache TTL of 1 hour (tokens valid for 24h, but we refresh sooner)
- Automatic cleanup of expired entries
"""

import base64
import hashlib
import json
import os
import time
from typing import Optional

import boto3
from botocore.exceptions import ClientError


# In-memory cache: token_hash → (customer_id, expiry_timestamp)
_customer_id_cache = {}
_CACHE_TTL = 3600  # 1 hour


def _decode_jwt_payload(token: str) -> dict:
    """Base64-decode the JWT payload. No verification — AgentCore already verified."""
    try:
        payload_b64 = token.split('.')[1]
        payload_b64 += '=' * (4 - len(payload_b64) % 4)
        return json.loads(base64.b64decode(payload_b64))
    except Exception:
        return {}


def _get_token_hash(token: str) -> str:
    """Generate a hash of the token for cache key (don't store full token)"""
    return hashlib.sha256(token.encode()).hexdigest()[:16]


def _clean_expired_cache():
    """Remove expired entries from cache"""
    now = time.time()
    expired = [k for k, (_, exp) in _customer_id_cache.items() if exp < now]
    for k in expired:
        del _customer_id_cache[k]


def extract_customer_id_from_token(access_token: str) -> Optional[str]:
    """
    Extract custom:customer_id from a Cognito access token with caching.

    This reduces Cognito API calls from N requests to 1 per unique token.
    Cache entries expire after 1 hour.

    Tries two methods on cache miss:
    1. get_user(AccessToken=...) — works for USER_PASSWORD_AUTH tokens that carry
       the 'aws.cognito.signin.user.admin' scope (API Token / get_mistral_token.py).
    2. AdminGetUser via IAM — works for OAuth 2.1 Authorization Code tokens that
       carry only OIDC scopes. Extracts username and user_pool_id from the JWT
       payload so no extra env vars are needed.
    """
    # Check cache first
    token_hash = _get_token_hash(access_token)
    now = time.time()

    if token_hash in _customer_id_cache:
        customer_id, expiry = _customer_id_cache[token_hash]
        if expiry > now:
            return customer_id
        else:
            # Expired entry - remove it
            del _customer_id_cache[token_hash]

    # Cache miss - call Cognito
    customer_id = _extract_customer_id_from_cognito(access_token)

    if customer_id:
        # Cache for 1 hour
        _customer_id_cache[token_hash] = (customer_id, now + _CACHE_TTL)

        # Periodic cleanup (every 100th entry to avoid overhead)
        if len(_customer_id_cache) > 100:
            _clean_expired_cache()

    return customer_id


def _extract_customer_id_from_cognito(access_token: str) -> Optional[str]:
    """
    Extract custom:customer_id from Cognito (original implementation).
    This is only called on cache miss.
    """
    region = os.environ.get('AWS_REGION', 'us-west-2')
    cognito = boto3.client('cognito-idp', region_name=region)

    # ── Method 1: get_user() ──────────────────────────────────────────────────
    # Works when the token scope includes aws.cognito.signin.user.admin
    try:
        user_info = cognito.get_user(AccessToken=access_token)
        for attr in user_info['UserAttributes']:
            if attr['Name'] == 'custom:customer_id':
                return attr['Value']
    except ClientError:
        pass

    # ── Method 2: AdminGetUser via IAM ────────────────────────────────────────
    # For OAuth 2.1 Authorization Code tokens (OIDC scopes only).
    # The JWT 'iss' claim is "https://cognito-idp.{region}.amazonaws.com/{pool_id}"
    # so we can derive the User Pool ID without an extra env var.
    try:
        payload = _decode_jwt_payload(access_token)

        # Cognito access tokens use 'username'; fallback to 'sub'
        username = payload.get('username') or payload.get('sub')

        # Extract pool ID from issuer: last path segment
        iss = payload.get('iss', '')
        user_pool_id = iss.rstrip('/').split('/')[-1]

        if username and user_pool_id:
            user_info = cognito.admin_get_user(
                UserPoolId=user_pool_id,
                Username=username,
            )
            for attr in user_info['UserAttributes']:
                if attr['Name'] == 'custom:customer_id':
                    return attr['Value']
    except (ClientError, Exception):
        pass

    return None


def get_cache_stats() -> dict:
    """Return cache statistics for monitoring (useful for debugging)"""
    now = time.time()
    active = sum(1 for _, exp in _customer_id_cache.values() if exp > now)
    expired = len(_customer_id_cache) - active
    return {
        "total_entries": len(_customer_id_cache),
        "active_entries": active,
        "expired_entries": expired
    }
