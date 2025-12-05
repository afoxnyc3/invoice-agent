"""
Health check endpoint for monitoring and CI/CD smoke tests.

Returns minimal system status to avoid information disclosure:
- status: healthy/degraded/unhealthy
- timestamp: ISO 8601 UTC timestamp

Detailed check results are logged server-side for troubleshooting
but not exposed in the public response.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any
import azure.functions as func
from shared.config import config
from shared.rate_limiter import rate_limit

logger = logging.getLogger(__name__)


def _check_storage_connectivity() -> tuple[bool, str]:
    """
    Check Azure Storage connectivity.

    Returns:
        tuple: (is_healthy, error_message or empty string)
    """
    try:
        # Attempt to list tables (lightweight operation)
        tables = list(config.table_service.list_tables())
        logger.debug(f"Storage check passed: {len(tables)} tables found")
        return True, ""
    except Exception as e:
        logger.error(f"Storage connectivity check failed: {e}")
        return False, str(e)


def _check_config() -> tuple[bool, list[str]]:
    """
    Validate required configuration.

    Returns:
        tuple: (is_healthy, list of missing config keys)
    """
    missing = config.validate_required()
    if missing:
        logger.error(f"Config validation failed: missing {missing}")
        return False, missing
    return True, []


@rate_limit(max_requests=60)  # Monitoring endpoint: 60 requests/minute
def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    Health check endpoint.

    Returns minimal JSON with system status for monitoring.
    Detailed errors are logged server-side but not exposed publicly.
    """
    try:
        # Collect health checks (results logged internally)
        storage_ok, storage_error = _check_storage_connectivity()
        config_ok, missing_config = _check_config()

        # Determine overall status
        all_healthy = storage_ok and config_ok

        # Minimal public response (no sensitive details)
        response = {
            "status": "healthy" if all_healthy else "degraded",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        status_code = 200 if all_healthy else 503
        return func.HttpResponse(
            json.dumps(response, indent=2),
            status_code=status_code,
            mimetype="application/json",
        )

    except Exception as e:
        # Log full error server-side, return minimal response publicly
        logger.error(f"Health check failed: {e}")
        return func.HttpResponse(
            json.dumps(
                {
                    "status": "unhealthy",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ),
            status_code=503,
            mimetype="application/json",
        )
