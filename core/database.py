import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from .config import get_settings


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL DEFAULT 'hrbp',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS interview_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    org_id TEXT NOT NULL DEFAULT 'default-org',
    department_id TEXT NOT NULL DEFAULT 'peopleops',
    candidate_name TEXT NOT NULL,
    interview_time TEXT NOT NULL,
    status TEXT NOT NULL,
    email_draft_path TEXT,
    calendar_event_path TEXT,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rag_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    question TEXT NOT NULL,
    expected_keywords TEXT NOT NULL,
    retrieved_sources TEXT NOT NULL,
    passed INTEGER NOT NULL,
    metrics_json TEXT DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approval_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    org_id TEXT NOT NULL DEFAULT 'default-org',
    department_id TEXT NOT NULL DEFAULT 'peopleops',
    action_type TEXT NOT NULL,
    subject_ref TEXT NOT NULL,
    status TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    approved_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    settings = get_settings()
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path)
    try:
        conn.executescript(SCHEMA)
        _ensure_columns(conn)
        conn.execute(
            """
            INSERT OR IGNORE INTO users (username, role, created_at)
            VALUES (?, ?, ?)
            """,
            ("local-admin", "admin", utc_now()),
        )
        conn.commit()
    finally:
        conn.close()


def _ensure_columns(conn: sqlite3.Connection) -> None:
    existing_interview_columns = {row[1] for row in conn.execute("PRAGMA table_info(interview_actions)").fetchall()}
    for column, definition in {
        "tenant_id": "TEXT NOT NULL DEFAULT 'default'",
        "org_id": "TEXT NOT NULL DEFAULT 'default-org'",
        "department_id": "TEXT NOT NULL DEFAULT 'peopleops'",
    }.items():
        if column not in existing_interview_columns:
            conn.execute(f"ALTER TABLE interview_actions ADD COLUMN {column} {definition}")

    existing_rag_columns = {row[1] for row in conn.execute("PRAGMA table_info(rag_evaluations)").fetchall()}
    if "tenant_id" not in existing_rag_columns:
        conn.execute("ALTER TABLE rag_evaluations ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'default'")
    if "metrics_json" not in existing_rag_columns:
        conn.execute("ALTER TABLE rag_evaluations ADD COLUMN metrics_json TEXT DEFAULT '{}'")


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    init_db()
    settings = get_settings()
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def create_interview_action(
    *,
    tenant_id: str = "default",
    org_id: str = "default-org",
    department_id: str = "peopleops",
    candidate_name: str,
    interview_time: str,
    status: str,
    email_draft_path: Optional[Path],
    calendar_event_path: Optional[Path],
    created_by: str,
) -> int:
    with get_conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO interview_actions (
                tenant_id,
                org_id,
                department_id,
                candidate_name,
                interview_time,
                status,
                email_draft_path,
                calendar_event_path,
                created_by,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tenant_id,
                org_id,
                department_id,
                candidate_name,
                interview_time,
                status,
                str(email_draft_path) if email_draft_path else None,
                str(calendar_event_path) if calendar_event_path else None,
                created_by,
                utc_now(),
            ),
        )
        return int(cursor.lastrowid)


def list_interview_actions(limit: int = 20, *, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        params: list[Any] = []
        tenant_clause = ""
        if tenant_id:
            tenant_clause = "WHERE tenant_id = ?"
            params.append(tenant_id)
        params.append(limit)
        rows = conn.execute(
            f"""
            SELECT *
            FROM interview_actions
            {tenant_clause}
            ORDER BY id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def create_rag_evaluation(
    *,
    tenant_id: str = "default",
    question: str,
    expected_keywords: str,
    retrieved_sources: str,
    passed: bool,
    metrics: Optional[Dict[str, Any]] = None,
) -> int:
    with get_conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO rag_evaluations (
                tenant_id,
                question,
                expected_keywords,
                retrieved_sources,
                passed,
                metrics_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (tenant_id, question, expected_keywords, retrieved_sources, int(passed), json_dumps(metrics or {}), utc_now()),
        )
        return int(cursor.lastrowid)


def json_dumps(value: Dict[str, Any]) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def create_approval_request(
    *,
    tenant_id: str,
    org_id: str,
    department_id: str,
    action_type: str,
    subject_ref: str,
    payload: Dict[str, Any],
    requested_by: str,
    status: str = "PENDING",
) -> int:
    timestamp = utc_now()
    with get_conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO approval_requests (
                tenant_id,
                org_id,
                department_id,
                action_type,
                subject_ref,
                status,
                payload_json,
                requested_by,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tenant_id,
                org_id,
                department_id,
                action_type,
                subject_ref,
                status,
                json_dumps(payload),
                requested_by,
                timestamp,
                timestamp,
            ),
        )
        return int(cursor.lastrowid)


def list_approval_requests(limit: int = 20, *, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        params: list[Any] = []
        tenant_clause = ""
        if tenant_id:
            tenant_clause = "WHERE tenant_id = ?"
            params.append(tenant_id)
        params.append(limit)
        rows = conn.execute(
            f"""
            SELECT *
            FROM approval_requests
            {tenant_clause}
            ORDER BY id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    return [dict(row) for row in rows]
