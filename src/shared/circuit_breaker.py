"""
Circuit breaker pattern for external dependencies.

Provides fail-fast behavior when external services are unavailable,
preventing cascade failures and resource exhaustion during outages.

Implements the circuit breaker pattern with three states:
- CLOSED: Normal operation, requests pass through
- OPEN: After fail_max failures, requests fail immediately
- HALF-OPEN: After reset_timeout, allows one test request

Dependencies protected:
- Microsoft Graph API (email operations)
- Azure OpenAI (PDF vendor extraction)
- Azure Blob Storage (PDF downloads)
"""

import logging
from functools import wraps
from typing import Callable, TypeVar, ParamSpec, Any, cast
from pybreaker import CircuitBreaker, CircuitBreakerError

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


# =============================================================================
# CIRCUIT BREAKER CONFIGURATION
# =============================================================================

# Graph API circuit breaker
# Opens after 5 consecutive failures, resets after 60 seconds
graph_breaker = CircuitBreaker(
    fail_max=5,
    reset_timeout=60,
    exclude=[ValueError, KeyError],  # Don't trip on validation errors
    name="graph_api",
)

# Azure OpenAI circuit breaker
# Opens after 3 consecutive failures, resets after 30 seconds
# More aggressive threshold since OpenAI failures are often systemic
openai_breaker = CircuitBreaker(
    fail_max=3,
    reset_timeout=30,
    exclude=[ValueError, KeyError],
    name="azure_openai",
)

# Azure Blob Storage circuit breaker
# Opens after 5 consecutive failures, resets after 45 seconds
storage_breaker = CircuitBreaker(
    fail_max=5,
    reset_timeout=45,
    exclude=[ValueError, KeyError],
    name="azure_storage",
)


# =============================================================================
# CIRCUIT BREAKER DECORATOR
# =============================================================================


def with_circuit_breaker(
    breaker: CircuitBreaker,
    fallback: Callable[..., Any] | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Decorator to wrap a function with circuit breaker protection.

    When the circuit is open, calls fail immediately without executing
    the wrapped function. This prevents resource exhaustion during outages.

    Args:
        breaker: CircuitBreaker instance to use
        fallback: Optional fallback function to call when circuit is open.
                  If not provided, CircuitBreakerError is raised.

    Returns:
        Decorated function with circuit breaker protection

    Example:
        >>> @with_circuit_breaker(graph_breaker)
        ... def call_graph_api():
        ...     return requests.get("https://graph.microsoft.com/...")
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            try:
                return breaker.call(func, *args, **kwargs)
            except CircuitBreakerError:
                logger.warning(
                    f"Circuit breaker '{breaker.name}' is OPEN - " f"failing fast (resets in {breaker.reset_timeout}s)"
                )
                if fallback is not None:
                    return cast(R, fallback(*args, **kwargs))
                raise

        return wrapper

    return decorator


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def get_circuit_state(breaker: CircuitBreaker) -> dict[str, Any]:
    """
    Get current state of a circuit breaker.

    Args:
        breaker: CircuitBreaker instance

    Returns:
        dict with state information:
            - name: Circuit breaker name
            - state: Current state (closed, open, half-open)
            - fail_count: Number of consecutive failures
            - fail_max: Threshold to open circuit
            - reset_timeout: Seconds until half-open
    """
    return {
        "name": breaker.name,
        "state": breaker.current_state,
        "fail_count": breaker.fail_counter,
        "fail_max": breaker.fail_max,
        "reset_timeout": breaker.reset_timeout,
    }


def get_all_circuit_states() -> dict[str, dict[str, Any]]:
    """
    Get current state of all circuit breakers.

    Returns:
        dict mapping circuit names to state information
    """
    return {
        "graph_api": get_circuit_state(graph_breaker),
        "azure_openai": get_circuit_state(openai_breaker),
        "azure_storage": get_circuit_state(storage_breaker),
    }


def reset_all_circuits() -> None:
    """
    Reset all circuit breakers to closed state.

    Use this for testing or manual recovery.
    """
    graph_breaker.close()
    openai_breaker.close()
    storage_breaker.close()
    logger.info("All circuit breakers reset to CLOSED state")
