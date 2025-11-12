"""
Retry utilities with exponential backoff for transient failures.

Provides decorators and functions to handle temporary failures
in external service calls (Graph API, Storage, Teams webhooks).
"""

import time
import logging
from functools import wraps
from typing import Callable, Type, Tuple, Optional


logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
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

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt < max_attempts:
                        logger.warning(
                            f"Attempt {attempt}/{max_attempts} failed: {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        logger.error(
                            f"All {max_attempts} attempts failed. " f"Last error: {e}"
                        )

            # All attempts exhausted, raise last exception
            raise last_exception

        return wrapper

    return decorator


def retry_with_timeout(
    func: Callable, max_attempts: int = 3, timeout_seconds: Optional[float] = None
) -> any:
    """
    Execute function with retry and optional timeout.

    Args:
        func: Function to execute
        max_attempts: Maximum retry attempts
        timeout_seconds: Optional timeout for entire operation

    Returns:
        Result from successful function execution

    Raises:
        Exception: Last exception if all attempts fail
        TimeoutError: If operation exceeds timeout

    Example:
        >>> result = retry_with_timeout(
        ...     lambda: api.call(),
        ...     max_attempts=3,
        ...     timeout_seconds=30.0
        ... )
    """
    start_time = time.time()
    delay = 1.0
    last_exception = None

    for attempt in range(1, max_attempts + 1):
        # Check timeout
        if timeout_seconds:
            elapsed = time.time() - start_time
            if elapsed >= timeout_seconds:
                raise TimeoutError(f"Operation timed out after {elapsed:.1f}s")

        try:
            return func()
        except Exception as e:
            last_exception = e

            if attempt < max_attempts:
                logger.warning(f"Attempt {attempt} failed, retrying...")
                time.sleep(delay)
                delay *= 2.0

    raise last_exception


class CircuitBreaker:
    """
    Circuit breaker pattern for handling cascading failures.

    Opens the circuit after consecutive failures to prevent
    overwhelming a failing service.
    """

    def __init__(self, failure_threshold: int = 5, timeout_seconds: float = 60.0):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Consecutive failures before opening
            timeout_seconds: Time before attempting to close circuit
        """
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.is_open = False

    def call(self, func: Callable) -> any:
        """
        Execute function through circuit breaker.

        Args:
            func: Function to execute

        Returns:
            Result from function

        Raises:
            Exception: If circuit is open or function fails
        """
        # Check if circuit should be closed
        if self.is_open:
            if time.time() - self.last_failure_time > self.timeout_seconds:
                logger.info("Circuit breaker: Attempting to close")
                self.is_open = False
                self.failure_count = 0
            else:
                raise Exception("Circuit breaker is OPEN")

        try:
            result = func()
            # Success, reset failure count
            self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                self.is_open = True
                logger.error(
                    f"Circuit breaker OPENED after " f"{self.failure_count} failures"
                )

            raise e
