"""
Health check endpoint for monitoring and CI/CD smoke tests.

Returns minimal system status by default to avoid information disclosure:
- status: healthy/degraded/unhealthy
- timestamp: ISO 8601 UTC timestamp

For internal monitoring, use ?detailed=true to get full dependency status:
- Circuit breaker states
- Deployment info (git SHA, timestamp)
- Individual dependency health checks
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any
import azure.functions as func
from shared.config import config
from shared.rate_limiter import rate_limit
from shared.circuit_breaker import get_all_circuit_states

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


def _check_graph_credentials() -> tuple[bool, str]:
    """
    Check if Graph API credentials are configured.

    Note: Does not make an actual API call to avoid latency.

    Returns:
        tuple: (is_healthy, error_message or empty string)
    """
    required = ["GRAPH_TENANT_ID", "GRAPH_CLIENT_ID", "GRAPH_CLIENT_SECRET"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        return False, f"Missing: {', '.join(missing)}"
    return True, ""


def _get_deployment_info() -> dict[str, Any]:
    """Get deployment information from environment variables."""
    return {
        "git_sha": os.environ.get("GIT_SHA", os.environ.get("SCM_COMMIT_ID", "unknown")),
        "deployment_timestamp": os.environ.get("DEPLOYMENT_TIMESTAMP", "unknown"),
        "environment": config.environment,
        "function_count": 9,
    }


def _get_detailed_health() -> dict[str, Any]:
    """
    Get detailed health information for internal monitoring.

    Includes sensitive data - only expose via ?detailed=true for
    internal monitoring systems.
    """
    storage_ok, storage_error = _check_storage_connectivity()
    config_ok, missing_config = _check_config()
    graph_ok, graph_error = _check_graph_credentials()
    circuit_states = get_all_circuit_states()

    circuits_healthy = all(state["state"] == "closed" for state in circuit_states.values())

    return {
        "checks": {
            "storage": {
                "healthy": storage_ok,
                "error": storage_error if not storage_ok else None,
            },
            "config": {
                "healthy": config_ok,
                "missing": missing_config if not config_ok else None,
            },
            "graph_credentials": {
                "healthy": graph_ok,
                "error": graph_error if not graph_ok else None,
            },
            "circuits": {
                "healthy": circuits_healthy,
                "states": circuit_states,
            },
        },
        "deployment": _get_deployment_info(),
        "all_healthy": storage_ok and config_ok and graph_ok and circuits_healthy,
    }


@rate_limit(max_requests=60)  # Monitoring endpoint: 60 requests/minute
def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    Health check endpoint.

    Query params:
        detailed: Set to 'true' for full dependency status (internal use only)

    Returns:
        200: All checks passed
        503: One or more checks failed
    """
    try:
        detailed = req.params.get("detailed", "").lower() == "true"

        if detailed:
            # Full health check with all details (internal monitoring)
            health_data = _get_detailed_health()

            response = {
                "status": "healthy" if health_data["all_healthy"] else "degraded",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "checks": health_data["checks"],
                "deployment": health_data["deployment"],
            }

            status_code = 200 if health_data["all_healthy"] else 503
        else:
            # Minimal public response (no sensitive details)
            storage_ok, _ = _check_storage_connectivity()
            config_ok, _ = _check_config()
            all_healthy = storage_ok and config_ok

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
