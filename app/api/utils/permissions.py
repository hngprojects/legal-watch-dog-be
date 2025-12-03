from enum import Enum


class Permission(str, Enum):
    """
    Granular permissions for RBAC system.
    Each permission controls access to specific operations.
    """

    # User Management
    MANAGE_USERS = "manage_users"
    INVITE_USERS = "invite_users"
    DEACTIVATE_USERS = "deactivate_users"
    ASSIGN_ROLES = "assign_roles"

    # Role Management
    CREATE_ROLES = "create_roles"
    EDIT_ROLES = "edit_roles"
    DELETE_ROLES = "delete_roles"
    VIEW_ROLES = "view_roles"

    # Organization Management
    MANAGE_ORGANIZATION = "manage_organization"
    CONFIGURE_SSO = "configure_sso"
    MANAGE_BILLING = "manage_billing"
    DELETE_ORGANIZATION = "delete_organization"

    # Project Management
    CREATE_PROJECTS = "create_projects"
    EDIT_PROJECTS = "edit_projects"
    DELETE_PROJECTS = "delete_projects"
    VIEW_PROJECTS = "view_projects"

    # Jurisdiction Management
    CREATE_JURISDICTIONS = "create_jurisdictions"
    EDIT_JURISDICTIONS = "edit_jurisdictions"
    DELETE_JURISDICTIONS = "delete_jurisdictions"
    VIEW_JURISDICTIONS = "view_jurisdictions"

    # Source Management
    CREATE_SOURCES = "create_sources"
    EDIT_SOURCES = "edit_sources"
    DELETE_SOURCES = "delete_sources"
    VIEW_SOURCES = "view_sources"
    TRIGGER_SCRAPING = "trigger_scraping"

    # Ticket Management
    CREATE_TICKETS = "create_tickets"
    EDIT_TICKETS = "edit_tickets"
    DELETE_TICKETS = "delete_tickets"
    VIEW_TICKETS = "view_tickets"
    ASSIGN_TICKETS = "assign_tickets"
    CLOSE_TICKETS = "close_tickets"

    # Participant Management
    INVITE_PARTICIPANTS = "invite_participants"
    REVOKE_PARTICIPANT_ACCESS = "revoke_participant_access"

    # Data & Revisions
    VIEW_REVISIONS = "view_revisions"
    EXPORT_DATA = "export_data"
    # Audit Viewing
    VIEW_AUDIT = "view_audit"

    # API Access
    MANAGE_API_KEYS = "manage_api_keys"

    @classmethod
    def validate_permissions(cls, permissions: dict) -> bool:
        """Validate that all permission keys are valid enum values."""
        valid_permissions = {perm.value for perm in cls}
        return all(perm in valid_permissions for perm in permissions.keys())

    @classmethod
    def get_all_permission_values(cls) -> list:
        """Get all available permission values as strings."""
        return [perm.value for perm in cls]


USER_PERMISSIONS = {
    Permission.VIEW_PROJECTS.value: True,
    Permission.VIEW_JURISDICTIONS.value: True,
    Permission.VIEW_SOURCES.value: True,
    Permission.VIEW_TICKETS.value: True,
    Permission.CREATE_TICKETS.value: True,
    Permission.EDIT_TICKETS.value: True,  # Their own tickets
    Permission.VIEW_REVISIONS.value: True,
}

# Predefined role permission sets
ADMIN_PERMISSIONS = {
    # Full access to everything
    Permission.MANAGE_USERS.value: True,
    Permission.INVITE_USERS.value: True,
    Permission.DEACTIVATE_USERS.value: True,
    Permission.ASSIGN_ROLES.value: True,
    Permission.CREATE_ROLES.value: True,
    Permission.EDIT_ROLES.value: True,
    Permission.DELETE_ROLES.value: True,
    Permission.VIEW_ROLES.value: True,
    Permission.MANAGE_ORGANIZATION.value: True,
    Permission.CONFIGURE_SSO.value: True,
    Permission.MANAGE_BILLING.value: True,
    Permission.CREATE_PROJECTS.value: True,
    Permission.EDIT_PROJECTS.value: True,
    Permission.DELETE_PROJECTS.value: True,
    Permission.VIEW_PROJECTS.value: True,
    Permission.CREATE_JURISDICTIONS.value: True,
    Permission.EDIT_JURISDICTIONS.value: True,
    Permission.DELETE_JURISDICTIONS.value: True,
    Permission.VIEW_JURISDICTIONS.value: True,
    Permission.CREATE_SOURCES.value: True,
    Permission.EDIT_SOURCES.value: True,
    Permission.DELETE_SOURCES.value: True,
    Permission.VIEW_SOURCES.value: True,
    Permission.TRIGGER_SCRAPING.value: True,
    Permission.CREATE_TICKETS.value: True,
    Permission.EDIT_TICKETS.value: True,
    Permission.DELETE_TICKETS.value: True,
    Permission.VIEW_TICKETS.value: True,
    Permission.ASSIGN_TICKETS.value: True,
    Permission.CLOSE_TICKETS.value: True,
    Permission.INVITE_PARTICIPANTS.value: True,
    Permission.REVOKE_PARTICIPANT_ACCESS.value: True,
    Permission.VIEW_REVISIONS.value: True,
    Permission.EXPORT_DATA.value: True,
    Permission.VIEW_AUDIT.value: True,
    Permission.MANAGE_API_KEYS.value: True,
}

MANAGER_PERMISSIONS = {
    # Can manage projects and tickets, but not organization settings
    Permission.INVITE_USERS.value: True,
    Permission.VIEW_ROLES.value: True,
    Permission.CREATE_PROJECTS.value: True,
    Permission.EDIT_PROJECTS.value: True,
    Permission.VIEW_PROJECTS.value: True,
    Permission.CREATE_JURISDICTIONS.value: True,
    Permission.EDIT_JURISDICTIONS.value: True,
    Permission.VIEW_JURISDICTIONS.value: True,
    Permission.CREATE_SOURCES.value: True,
    Permission.EDIT_SOURCES.value: True,
    Permission.VIEW_SOURCES.value: True,
    Permission.TRIGGER_SCRAPING.value: True,
    Permission.CREATE_TICKETS.value: True,
    Permission.EDIT_TICKETS.value: True,
    Permission.VIEW_TICKETS.value: True,
    Permission.ASSIGN_TICKETS.value: True,
    Permission.CLOSE_TICKETS.value: True,
    Permission.INVITE_PARTICIPANTS.value: True,
    Permission.VIEW_REVISIONS.value: True,
    Permission.EXPORT_DATA.value: True,
    Permission.VIEW_AUDIT.value: True,
}

OWNER_PERMISSIONS = {**ADMIN_PERMISSIONS, Permission.DELETE_ORGANIZATION.value: True}


class RoleTemplates:
    TEMPLATES = {
        "owner": OWNER_PERMISSIONS,
        "admin": ADMIN_PERMISSIONS,
        "manager": MANAGER_PERMISSIONS,
        "user": USER_PERMISSIONS,
    }

    @classmethod
    def get_template(cls, template_name: str) -> dict:
        return cls.TEMPLATES.get(template_name, {}).copy()

    @classmethod
    def get_available_templates(cls) -> list:
        return list(cls.TEMPLATES.keys())


class PermissionChecker:
    @staticmethod
    def has_permission(user_permissions: dict, permission: Permission) -> bool:
        return user_permissions.get(permission.value, False)

    @staticmethod
    def has_any_permission(user_permissions: dict, permissions: list) -> bool:
        return any(user_permissions.get(perm.value, False) for perm in permissions)
