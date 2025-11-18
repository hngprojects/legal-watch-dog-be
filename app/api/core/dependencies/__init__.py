"""
Core dependencies module.
"""
from app.api.core.dependencies.auth_dependencies import (
    get_current_user,
    get_current_active_user,
    get_client_ip,
    oauth2_scheme
)

__all__ = [
    "get_current_user",
    "get_current_active_user", 
    "get_client_ip",
    "oauth2_scheme"
]
