"""
Retry utilities with exponential backoff for transient failures.

Provides decorator to handle temporary failures in external service calls
(Graph API, Storage, Teams webhooks).
"""

import time
import logging
from functools import wraps
from typing import Callable, ParamSpec, TypeVar

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


def retry_with_backoff(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Decorator to retry function with exponential backoff.

    Retries the decorated function on failure with increasing delays:
    - Attempt 1: Immediate
    - Attempt 2: After initial_delay seconds
    - Attempt 3: After initial_delay * backoff_factor seconds
    - etc.

    Args:
        max_attempts: Maximum number of attempts (default: 3)
        initial_delay: Initial delay in seconds (default: 1.0)
        backoff_factor: Multiplier for each retry (default: 2.0)
        exceptions: Tuple of exception types to catch

    Returns:
        Decorated function with retry logic

    Example:
        >>> @retry_with_backoff(max_attempts=3, initial_delay=2.0)
        ... def fetch_data():
        ...     # May fail with transient error
        ...     return api.get_data()
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            delay = initial_delay
            last_exception: BaseException | None = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt < max_attempts:
                        logger.warning(f"Attempt {attempt}/{max_attempts} failed: {e}. " f"Retrying in {delay:.1f}s...")
                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        logger.error(f"All {max_attempts} attempts failed. " f"Last error: {e}")

            # All attempts exhausted, raise last exception
            if last_exception is not None:
                raise last_exception
            raise RuntimeError("Unexpected state: no exception but all attempts failed")

        return wrapper

    return decorator
