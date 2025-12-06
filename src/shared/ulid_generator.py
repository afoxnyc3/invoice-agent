"""
ULID (Universally Unique Lexicographically Sortable Identifier) generator.

ULIDs provide:
- Lexicographically sortable by creation time
- 128-bit compatibility with UUID
- Case-insensitive, URL-safe characters
- No special characters (safe for all systems)
"""

from datetime import datetime, timezone
from ulid import ULID


def generate_ulid() -> str:
    """
    Generate a new ULID for transaction tracking.

    Returns a string representation of a ULID that is:
    - Sortable by timestamp (first 48 bits)
    - Globally unique (remaining 80 bits of randomness)
    - URL-safe and case-insensitive

    Returns:
        str: ULID in string format (26 characters)

    Example:
        >>> ulid = generate_ulid()
        >>> print(ulid)
        '01JCK3Q7H8ZVXN3BARC9GWAEZM'
    """
    return str(ULID())


def utc_now_iso() -> str:
    """
    Get current UTC time in ISO 8601 format with Z suffix.

    Returns consistent timestamp format across the codebase:
    - Always UTC timezone
    - ISO 8601 format with Z suffix
    - Microsecond precision

    Returns:
        str: ISO 8601 timestamp (e.g., '2024-12-06T03:30:00.123456Z')

    Example:
        >>> timestamp = utc_now_iso()
        >>> print(timestamp)
        '2024-12-06T03:30:00.123456Z'
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
