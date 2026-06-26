from dataclasses import dataclass


def _clean_identifier(value: str | None, default: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        return default
    return "".join(ch for ch in cleaned if ch.isalnum() or ch in {"-", "_", "."})[:80] or default


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    org_id: str
    department_id: str

    @classmethod
    def from_headers(
        cls,
        *,
        tenant_id: str | None,
        org_id: str | None,
        department_id: str | None,
        default_tenant_id: str,
        default_org_id: str,
        default_department_id: str,
    ) -> "TenantContext":
        return cls(
            tenant_id=_clean_identifier(tenant_id, default_tenant_id),
            org_id=_clean_identifier(org_id, default_org_id),
            department_id=_clean_identifier(department_id, default_department_id),
        )

    def as_dict(self) -> dict[str, str]:
        return {
            "tenant_id": self.tenant_id,
            "org_id": self.org_id,
            "department_id": self.department_id,
        }
