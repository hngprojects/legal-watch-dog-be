"""
Audit Helper Utilities

Provides safe utilities for extracting request metadata, computing object
changes, and sanitizing sensitive information before persist­ing audit events.

These helpers are intentionally defensive: they never raise exceptions and
always return safe fallback values. This aligns with the audit service design
rule that audit failures should never break upstream application behavior.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import Request

logger = logging.getLogger(__name__)


def extract_audit_context(request: Request) -> Dict[str, Optional[str]]:
    """
    Safely extract IP address and User-Agent from a FastAPI request.

    This function never raises errors. If the request is missing client or
    header objects, it returns `"unknown"` as a fallback value.

    Args:
        request (Request): Incoming FastAPI request instance.

    Returns:
        Dict[str, Optional[str]]: A dictionary with:
            - "ip_address": The client's IP address or "unknown"
            - "user_agent": The user-agent string or "unknown"
    """
    try:
        ip_address = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        return {"ip_address": ip_address, "user_agent": user_agent}
    except Exception as e:
        logger.warning(
            "Failed to extract audit context: %s",
            str(e),
            exc_info=True,
        )
        return {"ip_address": "unknown", "user_agent": "unknown"}


def build_change_details(
    old_obj: Any,
    new_obj: Any,
    fields: List[str],
) -> Dict[str, Dict[str, Any]]:
    """
    Build a dictionary describing field-level changes between two objects.

    This function inspects each requested field, reading values with a
    defensive getter. Missing attributes do not raise errors. Only fields where
    old != new are included in the output.

    Args:
        old_obj (Any): Original object prior to modification.
        new_obj (Any): Updated object after modification.
        fields (List[str]): List of attribute names to inspect.

    Returns:
        Dict[str, Dict[str, Any]]: A mapping of:
            field_name -> {"old": old_value, "new": new_value}
        Only includes fields that differ.
    """
    changes: Dict[str, Dict[str, Any]] = {}

    for field in fields:
        try:
            old_value = getattr(old_obj, field, None)
            new_value = getattr(new_obj, field, None)

            if old_value != new_value:
                changes[field] = {"old": old_value, "new": new_value}
        except Exception as e:
            logger.warning(
                "Failed to compute change details for field '%s': %s",
                field,
                str(e),
                exc_info=True,
            )
            continue

    return changes


def sanitize_sensitive_data(
    details: Dict[str, Any],
    sensitive_fields: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Remove or mask sensitive fields in a details dictionary before it is stored
    inside audit logs.

    This function recursively processes nested dictionaries. Only the keys
    listed as sensitive are masked, not removed.

    Args:
        details (Dict[str, Any]):
            Original data dict to sanitize.
        sensitive_fields (Optional[List[str]]):
            List of sensitive field names to redact. Defaults to:
                ["password", "api_key", "token", "secret"]

    Returns:
        Dict[str, Any]: A sanitized copy of the details dictionary with
        sensitive fields masked.
    """
    if not isinstance(details, dict):
        logger.warning(
            "sanitize_sensitive_data received non-dict: %s",
            type(details),
        )
        return {}

    if sensitive_fields is None:
        sensitive_fields = ["password", "api_key", "token", "secret"]

    sanitized: Dict[str, Any] = details.copy()

    for field in sensitive_fields:
        if field in sanitized:
            sanitized[field] = "***REDACTED***"

    for key, value in sanitized.items():
        if isinstance(value, dict):
            sanitized[key] = sanitize_sensitive_data(value, sensitive_fields)

    return sanitized
