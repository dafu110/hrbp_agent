import json
from pathlib import Path
from typing import Any, Dict

from .config import get_settings


class LocalATSAdapter:
    """File-based adapter that keeps tool output portable until a real ATS is wired in."""

    def __init__(self, export_dir: Path | None = None) -> None:
        settings = get_settings()
        self.export_dir = export_dir or settings.ats_export_dir

    def sync_interview_action(self, action: Dict[str, Any]) -> Path:
        self.export_dir.mkdir(parents=True, exist_ok=True)
        export_path = self.export_dir / f"interview_action_{action['action_id']}.json"
        export_path.write_text(
            json.dumps(action, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return export_path
