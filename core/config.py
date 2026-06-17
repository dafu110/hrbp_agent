from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI


ROOT_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    api_key: Optional[str]
    api_base: Optional[str]
    chat_model: str
    embedding_model: str
    policy_pdf_path: Path
    rag_chunk_size: int
    rag_chunk_overlap: int
    rag_top_k: int

    @property
    def has_llm_config(self) -> bool:
        return bool(self.api_key and self.api_base)


def _int_env(name: str, default: int) -> int:
    import os

    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    import os

    load_dotenv()

    policy_pdf = os.getenv("HR_POLICY_PDF", "data/员工手册测试版.pdf")
    policy_pdf_path = Path(policy_pdf)
    if not policy_pdf_path.is_absolute():
        policy_pdf_path = ROOT_DIR / policy_pdf_path

    return Settings(
        api_key=os.getenv("OPENAI_API_KEY"),
        api_base=os.getenv("OPENAI_API_BASE"),
        chat_model=os.getenv("OPENAI_MODEL", "deepseek-chat"),
        embedding_model=os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
        policy_pdf_path=policy_pdf_path,
        rag_chunk_size=_int_env("RAG_CHUNK_SIZE", 400),
        rag_chunk_overlap=_int_env("RAG_CHUNK_OVERLAP", 40),
        rag_top_k=_int_env("RAG_TOP_K", 3),
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
