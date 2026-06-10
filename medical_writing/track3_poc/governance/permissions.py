"""
Simulated permission engine for the POC.

In production this would integrate with the company IdP and enforce 21 CFR
Part 11 electronic signature requirements. Here, role is set by the operator at
session start and the rules are applied in the UI without authentication.
"""
from enum import Enum


class Permission(str, Enum):
    READ = "read"
    SUGGEST = "suggest"
    EDIT = "edit"
    ACCEPT = "accept"
    LOCK = "lock"
    ADMIN = "admin"


ROLE_PERMISSIONS = {
    "regulatory_affairs": {
        "content_twin": [Permission.READ, Permission.EDIT, Permission.ACCEPT],
        "structure_twin": [Permission.READ, Permission.SUGGEST],
        "document_ra_sections": [Permission.READ, Permission.EDIT, Permission.ACCEPT, Permission.LOCK],
        "document_clinical_sections": [Permission.READ, Permission.SUGGEST],
    },
    "medical_writing": {
        "content_twin": [Permission.READ, Permission.EDIT],
        "structure_twin": [Permission.READ, Permission.EDIT, Permission.ACCEPT],
        "document_all_sections": [Permission.READ, Permission.EDIT, Permission.ACCEPT, Permission.LOCK],
    },
    "clinical_science": {
        "content_twin": [Permission.READ, Permission.SUGGEST],
        "structure_twin": [Permission.READ],
        "document_efficacy_sections": [Permission.READ, Permission.EDIT, Permission.ACCEPT],
        "document_other_sections": [Permission.READ, Permission.SUGGEST],
    },
    "clinical_operations": {
        "content_twin": [Permission.READ, Permission.SUGGEST],
        "structure_twin": [Permission.READ],
        "document_ops_sections": [Permission.READ, Permission.EDIT, Permission.ACCEPT],
        "document_other_sections": [Permission.READ, Permission.SUGGEST],
    },
    "biostatistician": {
        "content_twin": [Permission.READ, Permission.EDIT],  # stats elements only
        "structure_twin": [Permission.READ],
        "document_stats_sections": [Permission.READ, Permission.EDIT, Permission.ACCEPT],
        "document_other_sections": [Permission.READ, Permission.SUGGEST],
    },
    "qc_compliance": {
        "content_twin": [Permission.READ],
        "structure_twin": [Permission.READ],
        "document_all_sections": [Permission.READ],  # + QC sign-off authority (simulated)
    },
    "admin": {
        "content_twin": [Permission.READ, Permission.EDIT, Permission.ACCEPT, Permission.LOCK, Permission.ADMIN],
        "structure_twin": [Permission.READ, Permission.EDIT, Permission.ACCEPT, Permission.LOCK, Permission.ADMIN],
        "document_all_sections": [Permission.READ, Permission.EDIT, Permission.ACCEPT, Permission.LOCK, Permission.ADMIN],
    },
}


class PermissionEngine:
    def can(self, role: str, resource_type: str, permission: Permission) -> bool:
        role_perms = ROLE_PERMISSIONS.get(role, {})
        # Check exact resource type first, then the document_all_sections wildcard
        perms = role_perms.get(resource_type, role_perms.get("document_all_sections", []))
        return permission in perms

    def get_permissions(self, role: str, resource_type: str) -> list:
        role_perms = ROLE_PERMISSIONS.get(role, {})
        return role_perms.get(resource_type, role_perms.get("document_all_sections", []))
