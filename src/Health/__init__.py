"""
Health check endpoint for monitoring and CI/CD smoke tests.

Returns system status including:
- Function runtime status
- Storage connectivity
- Configuration validation
"""

import json
import logging
from datetime import datetime, timezone
import azure.functions as func
from shared.config import config
from shared.rate_limiter import rate_limit

logger = logging.getLogger(__name__)


def _check_storage_connectivity() -> dict:
    """Check Azure Storage connectivity."""
    try:
        # Attempt to list tables (lightweight operation)
        tables = list(config.table_service.list_tables())
        return {
            "status": "healthy",
            "tables_count": len(tables),
        }
    except Exception as e:
        logger.error(f"Storage connectivity check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
        }


def _check_config() -> dict:
    """Validate required configuration."""
    missing = config.validate_required()
    if missing:
        return {
            "status": "unhealthy",
            "missing_config": missing,
        }
    return {"status": "healthy"}


@rate_limit(max_requests=60)  # Monitoring endpoint: 60 requests/minute
def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    Health check endpoint.

    Returns JSON with system status for monitoring and CI/CD.
    """
    try:
        # Collect health checks
        storage_check = _check_storage_connectivity()
        config_check = _check_config()

        # Determine overall status
        checks_healthy = all(
            check.get("status") == "healthy"
            for check in [storage_check, config_check]
        )

        response = {
            "status": "healthy" if checks_healthy else "degraded",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "environment": config.environment,
            "checks": {
                "storage": storage_check,
                "config": config_check,
            },
        }

        status_code = 200 if checks_healthy else 503
        return func.HttpResponse(
            json.dumps(response, indent=2),
            status_code=status_code,
            mimetype="application/json",
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return func.HttpResponse(
            json.dumps({
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }),
            status_code=503,
            mimetype="application/json",
        )
