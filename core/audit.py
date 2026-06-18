import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from .config import get_settings
from .security import redact_payload


def _rotate_if_needed(path: Path, max_bytes: int) -> None:
    if max_bytes <= 0 or not path.exists() or path.stat().st_size < max_bytes:
        return
    rotated_path = path.with_name(
        f"{path.stem}.{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}{path.suffix}"
    )
    path.replace(rotated_path)


def write_audit_event(event_type: str, payload: Dict[str, Any]) -> None:
    settings = get_settings()
    settings.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
    _rotate_if_needed(settings.audit_log_path, settings.audit_log_max_bytes)

    safe_payload = redact_payload(payload)
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "payload": safe_payload,
    }

    with settings.audit_log_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event, ensure_ascii=False) + "\n")
