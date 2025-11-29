"""
Rate limiting module for HTTP endpoints.

Uses Azure Table Storage to track request counts by IP address.
Implements a sliding window algorithm with minute-based granularity.
"""

import logging
import os
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, ParamSpec, TypeVar
import azure.functions as func
from azure.core.exceptions import ResourceNotFoundError
from azure.data.tables import TableClient, TableServiceClient, UpdateMode

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


def get_client_ip(req: func.HttpRequest) -> str:
    """Extract client IP from request headers."""
    # X-Forwarded-For may contain multiple IPs, take the first (original client)
    forwarded: str = req.headers.get("X-Forwarded-For", "") or ""
    if forwarded:
        ip = forwarded.split(",")[0].strip()
        return ip if ip else "unknown"
    # Fallback to direct connection (rare in Azure Functions)
    real_ip: str = req.headers.get("X-Real-IP", "") or ""
    return real_ip if real_ip else "unknown"


def get_rate_limit_key(client_ip: str) -> tuple[str, str]:
    """
    Generate partition key and row key for rate limit tracking.

    Uses minute-based windows for automatic expiration.
    PartitionKey: "RateLimit"
    RowKey: "{IP}_{YYYYMMDD_HHMM}" (minute granularity)
    """
    # Normalize IP (replace dots/colons for Table Storage compatibility)
    normalized_ip = client_ip.replace(".", "_").replace(":", "_")
    minute_window = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    return "RateLimit", f"{normalized_ip}_{minute_window}"


def check_rate_limit(
    table_client: TableClient,
    client_ip: str,
    max_requests: int,
) -> tuple[bool, int]:
    """
    Check if client has exceeded rate limit.

    Args:
        table_client: Azure Table client for RateLimits table
        client_ip: Client IP address
        max_requests: Maximum requests allowed per minute

    Returns:
        Tuple of (is_allowed, current_count)
    """
    partition_key, row_key = get_rate_limit_key(client_ip)

    try:
        entity = table_client.get_entity(partition_key, row_key)
        current_count: int = entity.get("RequestCount", 0)

        if current_count >= max_requests:
            return False, current_count

        # Increment count
        entity["RequestCount"] = current_count + 1
        entity["LastRequest"] = datetime.now(timezone.utc).isoformat()
        table_client.update_entity(entity, mode=UpdateMode.MERGE)
        return True, current_count + 1

    except ResourceNotFoundError:
        # First request in this minute window - create entity
        entity_dict: dict[str, Any] = {
            "PartitionKey": partition_key,
            "RowKey": row_key,
            "RequestCount": 1,
            "ClientIP": client_ip,
            "FirstRequest": datetime.now(timezone.utc).isoformat(),
            "LastRequest": datetime.now(timezone.utc).isoformat(),
        }
        table_client.create_entity(entity_dict)
        return True, 1


def rate_limit_response(retry_after: int = 60) -> func.HttpResponse:
    """Generate 429 Too Many Requests response."""
    import json

    return func.HttpResponse(
        json.dumps(
            {
                "error": "Too Many Requests",
                "message": "Rate limit exceeded. Please try again later.",
                "retry_after": retry_after,
            }
        ),
        status_code=429,
        mimetype="application/json",
        headers={"Retry-After": str(retry_after)},
    )


def rate_limit(
    max_requests: int = 60, table_name: str = "RateLimits"
) -> Callable[[Callable[..., func.HttpResponse]], Callable[..., func.HttpResponse]]:
    """
    Decorator to add rate limiting to an Azure Function HTTP handler.

    Args:
        max_requests: Maximum requests per minute per IP (default: 60)
        table_name: Table Storage table name (default: "RateLimits")

    Usage:
        @rate_limit(max_requests=10)
        def main(req: func.HttpRequest) -> func.HttpResponse:
            ...
    """

    def decorator(func_handler: Callable[..., func.HttpResponse]) -> Callable[..., func.HttpResponse]:
        @wraps(func_handler)
        def wrapper(req: func.HttpRequest, *args: Any, **kwargs: Any) -> func.HttpResponse:
            # Skip rate limiting if disabled via environment
            if os.environ.get("RATE_LIMIT_DISABLED", "").lower() == "true":
                result = func_handler(req, *args, **kwargs)
                return result

            try:
                # Lazy import to avoid circular imports
                from shared.config import config

                client_ip = get_client_ip(req)
                table_client = config.get_table_client(table_name)

                is_allowed, count = check_rate_limit(table_client, client_ip, max_requests)

                if not is_allowed:
                    logger.warning(f"Rate limit exceeded for IP {client_ip}: " f"{count}/{max_requests} requests")
                    return rate_limit_response()

                logger.debug(f"Rate limit check passed for {client_ip}: " f"{count}/{max_requests}")

            except Exception as e:
                # On error, allow request but log warning
                # Fail open to avoid blocking legitimate traffic
                logger.warning(f"Rate limit check failed, allowing request: {e}")

            result = func_handler(req, *args, **kwargs)
            return result

        return wrapper

    return decorator


def create_rate_limit_table(table_service: TableServiceClient) -> None:
    """
    Create RateLimits table if it doesn't exist.

    Call this during deployment/initialization.
    """
    try:
        table_service.create_table_if_not_exists("RateLimits")
        logger.info("RateLimits table created or already exists")
    except Exception as e:
        logger.error(f"Failed to create RateLimits table: {e}")
        raise
