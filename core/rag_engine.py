import json
import shutil
from functools import lru_cache
from typing import Dict, List, Tuple

from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .audit import write_audit_event
from .config import get_chat_model, get_settings


def _source_label(doc: Document) -> str:
    settings = get_settings()
    page_num = int(doc.metadata.get("page", 0)) + 1
    return f"《{settings.policy_pdf_path.name}》第 {page_num} 页"


def _current_manifest() -> Dict[str, object]:
    settings = get_settings()
    stat = settings.policy_pdf_path.stat()
    return {
        "policy_pdf_path": str(settings.policy_pdf_path),
        "policy_pdf_size": stat.st_size,
        "policy_pdf_mtime": stat.st_mtime,
        "embedding_model": settings.embedding_model,
        "rag_chunk_size": settings.rag_chunk_size,
        "rag_chunk_overlap": settings.rag_chunk_overlap,
    }


def _read_manifest() -> Dict[str, object] | None:
    settings = get_settings()
    if not settings.rag_manifest_path.exists():
        return None
    try:
        return json.loads(settings.rag_manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _write_manifest(manifest: Dict[str, object]) -> None:
    settings = get_settings()
    settings.rag_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    settings.rag_manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def _has_persisted_index() -> bool:
    settings = get_settings()
    return settings.chroma_persist_dir.exists() and any(settings.chroma_persist_dir.iterdir())


def _index_is_current() -> bool:
    settings = get_settings()
    if not settings.policy_pdf_path.exists() or not _has_persisted_index():
        return False
    return _read_manifest() == _current_manifest()


def reset_rag_index() -> None:
    settings = get_settings()
    _build_retriever.cache_clear()
    if settings.chroma_persist_dir.exists():
        shutil.rmtree(settings.chroma_persist_dir)
    settings.chroma_persist_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def _build_retriever():
    settings = get_settings()
    if not settings.policy_pdf_path.exists():
        return None

    embeddings = HuggingFaceEmbeddings(model_name=settings.embedding_model)

    if _index_is_current():
        vectorstore = Chroma(
            persist_directory=str(settings.chroma_persist_dir),
            embedding_function=embeddings,
        )
    else:
        reset_rag_index()
        loader = PyPDFLoader(str(settings.policy_pdf_path))
        documents = loader.load()
        if not documents:
            return None

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.rag_chunk_size,
            chunk_overlap=settings.rag_chunk_overlap,
        )
        splits = splitter.split_documents(documents)
        vectorstore = Chroma.from_documents(
            documents=splits,
            embedding=embeddings,
            persist_directory=str(settings.chroma_persist_dir),
        )
        vectorstore.persist()
        _write_manifest(_current_manifest())
        write_audit_event(
            "rag.index_rebuilt",
            {
                "policy_pdf_path": str(settings.policy_pdf_path),
                "chunk_count": len(splits),
                "persist_directory": str(settings.chroma_persist_dir),
            },
        )

    return vectorstore.as_retriever(search_kwargs={"k": settings.rag_top_k})


def retrieve_policy_context(question: str) -> Tuple[str, List[str]]:
    retriever = _build_retriever()
    if retriever is None:
        settings = get_settings()
        raise FileNotFoundError(f"未找到企业知识库文件：{settings.policy_pdf_path}")

    docs = retriever.invoke(question)
    if not docs:
        return "", []

    context_parts = []
    sources = []
    for index, doc in enumerate(docs, start=1):
        context_parts.append(f"[片段{index} | {_source_label(doc)}]\n{doc.page_content}")
        sources.append(_source_label(doc))

    return "\n\n".join(context_parts), sorted(set(sources))


def retrieve_policy_evidence(question: str) -> List[Dict[str, str]]:
    retriever = _build_retriever()
    if retriever is None:
        return []

    docs = retriever.invoke(question)
    evidence = []
    for doc in docs:
        snippet = " ".join(doc.page_content.split())
        evidence.append(
            {
                "source": _source_label(doc),
                "snippet": snippet[:500],
            }
        )
    return evidence


def ask_rag(question: str) -> str:
    try:
        context_text, sources = retrieve_policy_context(question)
        if not context_text:
            write_audit_event("rag.no_context", {"question": question})
            return "未在企业知识库中检索到相关内容，请补充制度文档后再试。"

        llm = get_chat_model(temperature=0.1)
        template = """你是一个严谨的企业 HRBP 助手。请完全基于【参考文档】回答员工问题。
如果参考文档没有相关信息，请明确说明“文档中未找到相关规定”，不要编造。

【参考文档】
{context}

【员工问题】
{question}
"""
        prompt = ChatPromptTemplate.from_template(template).format(
            context=context_text,
            question=question,
        )
        response = llm.invoke(prompt)

        write_audit_event(
            "rag.answer",
            {
                "question": question,
                "sources": sources,
                "persist_directory": str(get_settings().chroma_persist_dir),
            },
        )

        sources_markdown = "\n".join([f"- {source}" for source in sources])
        return f"""{response.content}

---
#### 参考依据
{sources_markdown}
"""
    except Exception as exc:
        write_audit_event("rag.error", {"question": question, "error": str(exc)})
        return f"企业知识库检索失败：{exc}"
