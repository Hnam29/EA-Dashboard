"""
Định nghĩa các vai trò (Role) và ma trận phân quyền cho hệ thống EA Dashboard.
"""

from enum import Enum
from typing import Dict

class Role(str, Enum):
    ADMIN  = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"

# Ma trận quyền: role → permission → bool
PERMISSIONS: Dict[Role, Dict[str, bool]] = {
    Role.ADMIN: {
        "can_view":           True,
        "can_create":         True,
        "can_update":         True,
        "can_delete":         True,
        "can_manage_users":   True,
        "can_export":         True,
        "can_view_audit_log": True,
    },
    Role.EDITOR: {
        "can_view":           True,
        "can_create":         True,
        "can_update":         True,
        "can_delete":         False,
        "can_manage_users":   False,
        "can_export":         True,
        "can_view_audit_log": False,
    },
    Role.VIEWER: {
        "can_view":           True,
        "can_create":         False,
        "can_update":         False,
        "can_delete":         False,
        "can_manage_users":   False,
        "can_export":         False,
        "can_view_audit_log": False,
    },
}

ROLE_LABELS: Dict[str, str] = {
    "admin":  "🔴 Admin",
    "editor": "🟡 Editor",
    "viewer": "🟢 Viewer",
}

ROLE_BADGE_COLORS: Dict[str, str] = {
    "admin":  "#EF4444",
    "editor": "#F59E0B",
    "viewer": "#00B37E",
}


def has_permission(role: str, permission: str) -> bool:
    """Kiểm tra một role có quyền nhất định không."""
    try:
        role_enum = Role(role.lower())
    except ValueError:
        return False
    return PERMISSIONS.get(role_enum, {}).get(permission, False)


def get_role_label(role: str) -> str:
    return ROLE_LABELS.get(role.lower(), role)


def get_role_color(role: str) -> str:
    return ROLE_BADGE_COLORS.get(role.lower(), "#64748B")
