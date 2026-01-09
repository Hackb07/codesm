"""Permission system for tool execution.

This module provides a permission system that requires user confirmation
before executing potentially dangerous operations like git commands.
"""

from .permission import (
    Permission,
    PermissionRequest,
    PermissionResponse,
    PermissionDeniedError,
    ask_permission,
    respond_permission,
    get_pending_permissions,
    get_permission_manager,
    requires_permission,
    GIT_COMMANDS_REQUIRING_PERMISSION,
    DANGEROUS_COMMANDS,
)

__all__ = [
    "Permission",
    "PermissionRequest",
    "PermissionResponse",
    "PermissionDeniedError",
    "ask_permission",
    "respond_permission",
    "get_pending_permissions",
    "get_permission_manager",
    "requires_permission",
    "GIT_COMMANDS_REQUIRING_PERMISSION",
    "DANGEROUS_COMMANDS",
]
