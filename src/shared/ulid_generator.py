"""
ULID (Universally Unique Lexicographically Sortable Identifier) generator.

ULIDs provide:
- Lexicographically sortable by creation time
- 128-bit compatibility with UUID
- Case-insensitive, URL-safe characters
- No special characters (safe for all systems)
"""

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


def ulid_to_timestamp(ulid_str: str) -> float:
    """
    Extract the timestamp from a ULID string.

    Args:
        ulid_str: ULID string to parse

    Returns:
        float: Unix timestamp (seconds since epoch)

    Raises:
        ValueError: If the ULID string is invalid

    Example:
        >>> timestamp = ulid_to_timestamp('01JCK3Q7H8ZVXN3BARC9GWAEZM')
        >>> print(timestamp)
        1731160847.123
    """
    try:
        ulid_obj = ULID.from_str(ulid_str)
        return ulid_obj.timestamp()
    except Exception as e:
        raise ValueError(f"Invalid ULID format: {ulid_str}") from e
