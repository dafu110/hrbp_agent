from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI


ROOT_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    app_name: str
    api_key: Optional[str]
    api_base: Optional[str]
    chat_model: str
    embedding_model: str
    policy_pdf_path: Path
    chroma_persist_dir: Path
    rag_manifest_path: Path
    db_path: Path
    audit_log_path: Path
    email_draft_dir: Path
    calendar_dir: Path
    ats_export_dir: Path
    access_password: Optional[str]
    tool_execution_mode: str
    rag_chunk_size: int
    rag_chunk_overlap: int
    rag_top_k: int
    audit_log_max_bytes: int
    smtp_host: Optional[str]
    smtp_port: int
    smtp_username: Optional[str]
    smtp_password: Optional[str]
    smtp_from: str
    smtp_use_tls: bool

    @property
    def has_llm_config(self) -> bool:
        return bool(self.api_key and self.api_base)


def _path_env(name: str, default: str) -> Path:
    import os

    value = Path(os.getenv(name, default))
    if value.is_absolute():
        return value
    return ROOT_DIR / value


def _int_env(name: str, default: int) -> int:
    import os

    value = os.getenv(name)
    if not value:
        return default


def _bool_env(name: str, default: bool) -> bool:
    import os

    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
    try:
        return int(value)
    except ValueError:
        return default


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    import os

    load_dotenv()

    return Settings(
        app_name=os.getenv("APP_NAME", "PeopleOps Agent Platform"),
        api_key=os.getenv("OPENAI_API_KEY"),
        api_base=os.getenv("OPENAI_API_BASE"),
        chat_model=os.getenv("OPENAI_MODEL", "deepseek-chat"),
        embedding_model=os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5"),
        policy_pdf_path=_path_env("HR_POLICY_PDF", "data/员工手册测试版.pdf"),
        chroma_persist_dir=_path_env("CHROMA_PERSIST_DIR", ".chroma/policy"),
        rag_manifest_path=_path_env("RAG_MANIFEST_PATH", ".chroma/policy/manifest.json"),
        db_path=_path_env("APP_DB_PATH", ".runtime/peopleops.sqlite3"),
        audit_log_path=_path_env("AUDIT_LOG_PATH", ".runtime/audit/events.jsonl"),
        email_draft_dir=_path_env("EMAIL_DRAFT_DIR", ".runtime/email_drafts"),
        calendar_dir=_path_env("CALENDAR_DIR", ".runtime/calendar"),
        ats_export_dir=_path_env("ATS_EXPORT_DIR", ".runtime/ats_exports"),
        access_password=os.getenv("ACCESS_PASSWORD"),
        tool_execution_mode=os.getenv("TOOL_EXECUTION_MODE", "local"),
        rag_chunk_size=_int_env("RAG_CHUNK_SIZE", 400),
        rag_chunk_overlap=_int_env("RAG_CHUNK_OVERLAP", 40),
        rag_top_k=_int_env("RAG_TOP_K", 3),
        audit_log_max_bytes=_int_env("AUDIT_LOG_MAX_BYTES", 5_000_000),
        smtp_host=os.getenv("SMTP_HOST"),
        smtp_port=_int_env("SMTP_PORT", 587),
        smtp_username=os.getenv("SMTP_USERNAME"),
        smtp_password=os.getenv("SMTP_PASSWORD"),
        smtp_from=os.getenv("SMTP_FROM", "hr@example.com"),
        smtp_use_tls=_bool_env("SMTP_USE_TLS", True),
    )


def get_chat_model(*, temperature: float = 0.0) -> ChatOpenAI:
    settings = get_settings()
    if not settings.has_llm_config:
        raise RuntimeError("缺少 OPENAI_API_KEY 或 OPENAI_API_BASE，请先配置 .env。")

    return ChatOpenAI(
        model=settings.chat_model,
        api_key=settings.api_key,
        base_url=settings.api_base,
        temperature=temperature,
    )
