from functools import lru_cache
from typing import List, Tuple

from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .config import get_chat_model, get_settings


def _source_label(doc: Document) -> str:
    settings = get_settings()
    page_num = int(doc.metadata.get("page", 0)) + 1
    return f"《{settings.policy_pdf_path.name}》第 {page_num} 页"


@lru_cache(maxsize=1)
def _build_retriever():
    settings = get_settings()
    if not settings.policy_pdf_path.exists():
        return None

    loader = PyPDFLoader(str(settings.policy_pdf_path))
    documents = loader.load()
    if not documents:
        return None

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.rag_chunk_size,
        chunk_overlap=settings.rag_chunk_overlap,
    )
    splits = splitter.split_documents(documents)
    embeddings = HuggingFaceEmbeddings(model_name=settings.embedding_model)
    vectorstore = Chroma.from_documents(documents=splits, embedding=embeddings)
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


def ask_rag(question: str) -> str:
    try:
        context_text, sources = retrieve_policy_context(question)
        if not context_text:
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

        sources_markdown = "\n".join([f"- {source}" for source in sources])
        return f"""{response.content}

---
#### 参考依据
{sources_markdown}
"""
    except Exception as exc:
        return f"企业知识库检索失败：{exc}"
