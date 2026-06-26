from dataclasses import dataclass
from typing import Iterable

from .config import get_settings
from .security import verify_password


@dataclass(frozen=True)
class Principal:
    username: str
    role: str
    tenant_id: str = "default"
    org_id: str = "default-org"
    department_id: str = "peopleops"

    def scope(self) -> dict[str, str]:
        return {
            "tenant_id": self.tenant_id,
            "org_id": self.org_id,
            "department_id": self.department_id,
        }


ROLE_PERMISSIONS = {
    "admin": {"chat", "resume", "rag", "tool", "audit", "users"},
    "hrbp": {"chat", "resume", "rag", "tool"},
    "viewer": {"chat", "rag"},
}


def authenticate_with_password(password: str) -> Principal | None:
    settings = get_settings()
    if verify_password(password, settings.access_password):
        return Principal(username="local-admin", role="admin")
    return None


def has_permission(principal: Principal, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(principal.role, set())


def require_permission(principal: Principal, permission: str) -> None:
    if not has_permission(principal, permission):
        raise PermissionError(f"User {principal.username} lacks permission: {permission}")


def allowed_permissions(role: str) -> Iterable[str]:
    return sorted(ROLE_PERMISSIONS.get(role, set()))
