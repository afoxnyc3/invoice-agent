"""
Structured logging utility with correlation ID support.

Provides consistent logging format across all Azure Functions with
automatic correlation ID injection for distributed tracing.
"""

import logging
import sys
from typing import Optional


class CorrelatedLogger:
    """
    Logger wrapper that includes correlation ID in all log messages.

    Enables distributed tracing across the invoice processing pipeline
    by including the transaction ULID in every log entry.
    """

    def __init__(self, name: str, correlation_id: str):
        """
        Initialize logger with correlation ID.

        Args:
            name: Logger name (typically __name__)
            correlation_id: ULID transaction identifier
        """
        self.logger = logging.getLogger(name)
        self.correlation_id = correlation_id

    def _format_message(self, message: str) -> str:
        """Add correlation ID prefix to message."""
        return f"[{self.correlation_id}] {message}"

    def debug(self, message: str, **kwargs):
        """Log debug message with correlation ID."""
        self.logger.debug(self._format_message(message), **kwargs)

    def info(self, message: str, **kwargs):
        """Log info message with correlation ID."""
        self.logger.info(self._format_message(message), **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message with correlation ID."""
        self.logger.warning(self._format_message(message), **kwargs)

    def error(self, message: str, **kwargs):
        """Log error message with correlation ID."""
        self.logger.error(self._format_message(message), **kwargs)

    def exception(self, message: str, **kwargs):
        """Log exception with correlation ID."""
        self.logger.exception(self._format_message(message), **kwargs)


def get_logger(
    name: str, correlation_id: str, level: Optional[int] = None
) -> CorrelatedLogger:
    """
    Get a correlated logger instance.

    Args:
        name: Logger name (use __name__ for current module)
        correlation_id: ULID transaction identifier
        level: Optional logging level (default: INFO)

    Returns:
        CorrelatedLogger: Logger with correlation ID support

    Example:
        >>> logger = get_logger(__name__, transaction_id)
        >>> logger.info("Processing invoice")
        [01JCK3Q7H8ZVXN3BARC9GWAEZM] Processing invoice
    """
    # Configure logging if not already configured
    logger = logging.getLogger(name)

    if level is not None:
        logger.setLevel(level)
    elif not logger.handlers:
        # Default configuration
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return CorrelatedLogger(name, correlation_id)
