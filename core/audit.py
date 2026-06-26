import contextvars
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

from .config import get_settings
from .security import redact_payload


_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)
_actor: contextvars.ContextVar[str | None] = contextvars.ContextVar("actor", default=None)
_tenant_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("tenant_id", default=None)
_org_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("org_id", default=None)
_department_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("department_id", default=None)


def set_audit_context(
    *,
    request_id: str | None = None,
    actor: str | None = None,
    tenant_id: str | None = None,
    org_id: str | None = None,
    department_id: str | None = None,
) -> None:
    if request_id is not None:
        _request_id.set(request_id)
    if actor is not None:
        _actor.set(actor)
    if tenant_id is not None:
        _tenant_id.set(tenant_id)
    if org_id is not None:
        _org_id.set(org_id)
    if department_id is not None:
        _department_id.set(department_id)


def clear_audit_context() -> None:
    _request_id.set(None)
    _actor.set(None)
    _tenant_id.set(None)
    _org_id.set(None)
    _department_id.set(None)


def get_request_id() -> str | None:
    return _request_id.get()


def _rotate_if_needed(path: Path, max_bytes: int) -> None:
    if max_bytes <= 0 or not path.exists() or path.stat().st_size < max_bytes:
        return
    rotated_path = path.with_name(
        f"{path.stem}.{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}{path.suffix}"
    )
    path.replace(rotated_path)


def _hash_event(event: Dict[str, Any]) -> str:
    encoded = json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _last_event_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    last_hash: str | None = None
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            try:
                last_hash = json.loads(line).get("event_hash") or last_hash
            except json.JSONDecodeError:
                continue
    return last_hash


def write_audit_event(event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    settings = get_settings()
    settings.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
    _rotate_if_needed(settings.audit_log_path, settings.audit_log_max_bytes)

    event = {
        "schema_version": "2026-06-24",
        "event_id": uuid4().hex,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": get_request_id(),
        "actor": _actor.get(),
        "tenant_id": _tenant_id.get(),
        "org_id": _org_id.get(),
        "department_id": _department_id.get(),
        "event_type": event_type,
        "payload": redact_payload(payload),
    }
    if settings.audit_hash_chain_enabled:
        event["previous_event_hash"] = _last_event_hash(settings.audit_log_path)
        event["event_hash"] = _hash_event(event)

    with settings.audit_log_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def read_audit_events(limit: int = 50) -> List[Dict[str, Any]]:
    settings = get_settings()
    if not settings.audit_log_path.exists():
        return []
    events: List[Dict[str, Any]] = []
    with settings.audit_log_path.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                events.append({"event_type": "audit.corrupt_line", "raw": line.strip()[:200]})
    return events[-limit:]


def verify_audit_integrity() -> Dict[str, Any]:
    settings = get_settings()
    if not settings.audit_log_path.exists():
        return {"valid": True, "total_events": 0, "errors": [], "last_event_hash": None}

    errors: List[Dict[str, Any]] = []
    previous_hash: str | None = None
    total = 0
    with settings.audit_log_path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append({"line": line_number, "error": f"invalid_json: {exc}"})
                continue

            total += 1
            expected_previous = event.get("previous_event_hash")
            if expected_previous != previous_hash:
                errors.append(
                    {
                        "line": line_number,
                        "error": "previous_event_hash_mismatch",
                        "expected": previous_hash,
                        "actual": expected_previous,
                    }
                )

            event_hash = event.get("event_hash")
            event_for_hash = copy.deepcopy(event)
            event_for_hash.pop("event_hash", None)
            expected_hash = _hash_event(event_for_hash)
            if event_hash != expected_hash:
                errors.append(
                    {
                        "line": line_number,
                        "error": "event_hash_mismatch",
                        "expected": expected_hash,
                        "actual": event_hash,
                    }
                )
            previous_hash = event_hash

    return {
        "valid": not errors,
        "total_events": total,
        "errors": errors,
        "last_event_hash": previous_hash,
    }
