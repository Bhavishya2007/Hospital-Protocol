"""Role-Based Access Control (RBAC) Module for Hospital Protocol Resolver."""

from typing import Dict, Tuple
from src.models import Document


VALID_ROLES = {"Nurse", "Physician", "Pharmacist", "Clinical_Admin", "Visitor"}


def check_role_access(
    document_id: str,
    user_role: str,
    access_map: Dict[Tuple[str, str], bool],
) -> Tuple[bool, str]:
    """Checks if the user role is permitted to view the protocol."""
    if user_role not in VALID_ROLES:
        return False, f"Unrecognized clinical role: '{user_role}'. Access denied."

    # Look up specific permission in access_map
    key = (document_id, user_role)
    if key in access_map:
        allowed = access_map[key]
        if allowed:
            return True, f"Role '{user_role}' authorized for document '{document_id}'."
        else:
            return False, f"Role '{user_role}' explicitly restricted from document '{document_id}'."

    # Fallback to default policy based on document prefix or default permit for clinical staff
    if user_role == "Visitor":
        return False, f"Role 'Visitor' restricted from internal clinical documents."
    return True, f"Default clinical access granted to role '{user_role}'."
