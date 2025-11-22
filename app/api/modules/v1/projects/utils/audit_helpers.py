# app/api/modules/v1/projects/utils/audit_helpers.py
"""
Helper utilities for audit logging
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import Request

logger = logging.getLogger(__name__)


def extract_audit_context(request: Request) -> Dict[str, Optional[str]]:
    """
    Extract IP address and user agent from FastAPI request safely.

    Returns default values if client or headers are missing.
    """
    try:
        ip_address = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        return {"ip_address": ip_address, "user_agent": user_agent}
    except Exception as e:
        logger.warning("Failed to extract audit context: %s", str(e), exc_info=True)
        return {"ip_address": "unknown", "user_agent": "unknown"}


def build_change_details(
    old_obj: Any,
    new_obj: Any,
    fields: List[str]
) -> Dict[str, Dict[str, Any]]:
    """
    Build change details for audit log from old/new objects.
    Ignores missing attributes and avoids raising exceptions.

    Args:
        old_obj: Original object
        new_obj: Updated object
        fields: List of field names to track

    Returns:
        {"field_name": {"old": "value", "new": "value"}}
    """

    changes = {}

    for field in fields:
        try:
            old_value = getattr(old_obj, field, None)
            new_value = getattr(new_obj, field, None)

            if old_value != new_value:
                changes[field] = {"old": old_value, "new": new_value}
        except Exception as e:
            logger.warning(
                "Failed to get change details for field '%s': %s",
                field,
                str(e),
                exc_info=True
            )
            continue

    return changes



def sanitize_sensitive_data(
    details: Dict[str, Any],
    sensitive_fields: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Remove or mask sensitive data from audit log details.
    Handles nested dictionaries safely.

    Args:
        details: Original details dictionary
        sensitive_fields: List of fields to redact (default: [
    "password", "api_key", "token", "secret"
    ])


    Returns:
        Sanitized details dictionary
    """
    if not isinstance(details, dict):
        logger.warning("sanitize_sensitive_data received non-dict details: %s", type(details))
        return {}

    if sensitive_fields is None:
        sensitive_fields = ["password", "api_key", "token", "secret"]

    sanitized = details.copy()

    for field in sensitive_fields:
        if field in sanitized:
            sanitized[field] = "***REDACTED***"

    # Handle nested dictionaries
    for key, value in sanitized.items():
        if isinstance(value, dict):
            sanitized[key] = sanitize_sensitive_data(value, sensitive_fields)

    return sanitized
