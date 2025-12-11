"""
Fuzzy vendor name matching using rapidfuzz.

Provides intelligent matching for vendor names that may have variations:
- "Adobe Systems Incorporated" -> matches "Adobe Inc"
- "Microsoft Corporation" -> matches "Microsoft"
- "Amazon Web Services" -> matches "AWS"

Uses token_sort_ratio for best results with varying word order.
"""

import logging
import os
from typing import Any

from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)

# Default threshold - configurable via environment variable
# Set to 75 for better cross-version compatibility with rapidfuzz
DEFAULT_FUZZY_THRESHOLD = 75
FUZZY_THRESHOLD = int(os.environ.get("VENDOR_FUZZY_THRESHOLD", DEFAULT_FUZZY_THRESHOLD))


def find_fuzzy_match(
    search_name: str,
    vendors: list[dict[str, Any]],
    threshold: int | None = None,
) -> tuple[dict[str, Any] | None, int]:
    """
    Find the best fuzzy match for a vendor name.

    Args:
        search_name: The vendor name to search for (e.g., "Adobe Systems Inc")
        vendors: List of vendor entities from VendorMaster table
        threshold: Minimum match score (0-100). Defaults to FUZZY_THRESHOLD env var.

    Returns:
        Tuple of (matched_vendor, confidence_score) or (None, 0) if no match found.
        Confidence score is 0-100 indicating match quality.
    """
    if not search_name or not vendors:
        return None, 0

    if threshold is None:
        threshold = FUZZY_THRESHOLD

    search_lower = search_name.lower().strip()

    # Build choices dict: normalized_name -> vendor entity
    choices = {}
    for vendor in vendors:
        vendor_name = vendor.get("VendorName", "")
        if vendor_name:
            choices[vendor_name.lower()] = vendor

    if not choices:
        return None, 0

    # Use WRatio - weighted combination of multiple fuzzy matching algorithms
    # Handles partial matches, word order differences, and suffix variations well
    # "Adobe Systems Incorporated" vs "Adobe Inc" -> high score
    result = process.extractOne(
        search_lower,
        list(choices.keys()),
        scorer=fuzz.WRatio,
    )

    if result is None:
        return None, 0

    matched_name, score, _ = result

    if score >= threshold:
        vendor = choices[matched_name]
        logger.info(f"Fuzzy match: '{search_name}' -> '{vendor['VendorName']}' (score: {score})")
        return vendor, score

    logger.debug(
        f"Fuzzy match below threshold: '{search_name}' best match '{matched_name}' (score: {score}, threshold: {threshold})"
    )
    return None, score


def normalize_vendor_name(name: str) -> str:
    """
    Normalize vendor name for comparison.

    Removes common suffixes and normalizes whitespace:
    - "Adobe Inc." -> "adobe"
    - "Microsoft Corporation" -> "microsoft"
    - "Amazon Web Services, LLC" -> "amazon web services"
    """
    if not name:
        return ""

    # Lowercase and strip
    normalized = name.lower().strip()

    # Remove common legal suffixes
    suffixes = [
        ", inc.",
        ", inc",
        " inc.",
        " inc",
        ", llc",
        " llc",
        ", ltd",
        " ltd",
        ", ltd.",
        " ltd.",
        " corporation",
        " corp.",
        " corp",
        " co.",
        " co",
        ", co",
        " limited",
        " gmbh",
        " ag",
        " plc",
        " s.a.",
        " sa",
    ]

    for suffix in suffixes:
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
            break

    # Normalize whitespace
    normalized = " ".join(normalized.split())

    return normalized


def get_all_vendor_names(vendors: list[dict[str, Any]]) -> list[str]:
    """
    Extract all vendor names from vendor entities.

    Useful for building autocomplete lists or validation.
    """
    return [v.get("VendorName", "") for v in vendors if v.get("VendorName")]
