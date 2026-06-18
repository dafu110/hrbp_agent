import time
from uuid import uuid4

import streamlit as st

from core.audit import write_audit_event
from core.config import get_settings
from core.database import init_db, list_interview_actions
from core.pdf_utils import extract_document_text
from core.rag_engine import retrieve_policy_evidence
from core.security import stable_hash, verify_password
from core.workflow import agent_app


settings = get_settings()
init_db()
st.set_page_config(page_title=settings.app_name, page_icon="💼", layout="wide")
st.markdown(
    """
    <style>
    .block-container {padding-top: 1.6rem; max-width: 1180px;}
    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 12px 14px;
    }
    section[data-testid="stSidebar"] {
        border-right: 1px solid #e5e7eb;
    }
    .small-muted {color: #6b7280; font-size: 0.88rem;}
    </style>
    """,
    unsafe_allow_html=True,
)
st.title(settings.app_name)
st.caption("HRBP Agent 工作台：制度问答、简历/JD 匹配、面试邀约与审计留痕")


@st.cache_data(show_spinner=False)
def cached_extract_document_text(file_bytes: bytes, filename: str) -> str:
    return extract_document_text(file_bytes, filename)


def init_state() -> None:
    st.session_state.setdefault("extracted_resume_text", "")
    st.session_state.setdefault("resume_file_names", [])
    st.session_state.setdefault("thread_id", f"peopleops_session_{uuid4().hex[:8]}")
    st.session_state.setdefault("authenticated", not bool(settings.access_password))
    st.session_state.setdefault(
        "messages",
        [
            {
                "role": "assistant",
                "content": (
                    "您好，我是 PeopleOps Agent。您可以上传候选人简历并粘贴 JD 做匹配评估，"
                    "也可以询问员工手册、考勤、报销、福利等制度问题。"
                ),
            }
        ],
    )


def render_stream(text: str) -> None:
    placeholder = st.empty()
    displayed = ""
    for chunk in text:
        displayed += chunk
        placeholder.markdown(displayed + "▌")
        time.sleep(0.002)
    placeholder.markdown(text)


def require_access() -> None:
    if st.session_state.get("authenticated"):
        return

    st.info("请输入访问口令以进入 PeopleOps Agent Platform。")
    password = st.text_input("访问口令", type="password")
    if st.button("进入", type="primary"):
        if verify_password(password, settings.access_password):
            st.session_state["authenticated"] = True
            write_audit_event("auth.login_success", {"session_id": st.session_state["thread_id"]})
            st.rerun()
        write_audit_event("auth.login_failed", {"session_id": st.session_state["thread_id"]})
        st.error("访问口令不正确。")
    st.stop()


init_state()
require_access()

with st.sidebar:
    st.header("候选人与上下文")
    uploaded_resumes = st.file_uploader(
        "导入简历文件",
        type=["pdf", "docx", "txt", "md"],
        accept_multiple_files=True,
        help="支持 PDF、Word DOCX、TXT、Markdown，可一次导入多份候选人材料。",
    )

    if uploaded_resumes:
        try:
            extracted_parts = []
            file_names = []
            with st.spinner("正在提取简历文本..."):
                for uploaded_resume in uploaded_resumes:
                    text_content = cached_extract_document_text(
                        uploaded_resume.getvalue(),
                        uploaded_resume.name,
                    )
                    if text_content:
                        file_names.append(uploaded_resume.name)
                        extracted_parts.append(f"【文件：{uploaded_resume.name}】\n{text_content}")

            combined_text = "\n\n".join(extracted_parts).strip()
            st.session_state["extracted_resume_text"] = combined_text
            st.session_state["resume_file_names"] = file_names
            if combined_text:
                write_audit_event(
                    "resume.uploaded",
                    {
                        "session_id": st.session_state["thread_id"],
                        "filenames": file_names,
                        "content_hash": stable_hash(combined_text),
                        "char_count": len(combined_text),
                    },
                )
                st.success(f"已导入 {len(file_names)} 个文件")
            else:
                st.warning("未提取到可用文本，可能是扫描件、图片型简历或空文件。")
        except Exception as exc:
            st.session_state["extracted_resume_text"] = ""
            st.session_state["resume_file_names"] = []
            write_audit_event(
                "resume.upload_failed",
                {"session_id": st.session_state["thread_id"], "error": str(exc)},
            )
            st.error(f"简历解析失败：{exc}")
    else:
        st.session_state["extracted_resume_text"] = ""
        st.session_state["resume_file_names"] = []

    jd_input = st.text_area(
        "岗位描述（JD）",
        height=260,
        placeholder="粘贴岗位职责、任职要求、技术栈、年限要求等信息...",
    )

    if st.session_state["extracted_resume_text"]:
        with st.expander("简历文本预览", expanded=False):
            st.text(st.session_state["extracted_resume_text"][:3000])

    st.divider()
    st.subheader("运行状态")
    if not settings.policy_pdf_path.exists():
        st.warning("未找到企业知识库 PDF，请检查 HR_POLICY_PDF 配置。")
    if not settings.has_llm_config:
        st.warning("未配置 OPENAI_API_KEY 或 OPENAI_API_BASE，系统将只能使用部分降级能力。")
    if settings.access_password:
        st.success("访问控制已开启")
    else:
        st.warning("访问控制未开启，可配置 ACCESS_PASSWORD。")

    st.divider()
    st.subheader("知识库引用预检")
    preview_question = st.text_input("检索问题", placeholder="例如：出差报销有什么标准？")
    if st.button("预览引用", use_container_width=True) and preview_question.strip():
        evidence = retrieve_policy_evidence(preview_question.strip())
        if evidence:
            for item in evidence:
                st.caption(item["source"])
                st.write(item["snippet"])
        else:
            st.warning("未检索到引用片段。")

    st.divider()
    st.subheader("最近工具动作")
    for action in list_interview_actions(limit=5):
        st.caption(
            f"#{action['id']} {action['status']} | {action['candidate_name']} | {action['interview_time']}"
        )

status_cols = st.columns(4)
with status_cols[0]:
    st.metric("会话", st.session_state["thread_id"])
with status_cols[1]:
    st.metric("简历文件", len(st.session_state["resume_file_names"]))
with status_cols[2]:
    st.metric("工具模式", settings.tool_execution_mode)
with status_cols[3]:
    st.metric("知识库", settings.policy_pdf_path.name)

st.divider()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


if user_input := st.chat_input("请输入 HR 问题、制度问题或候选人评估需求..."):
    st.session_state.messages.append({"role": "user", "content": user_input})
    write_audit_event(
        "chat.user_message",
        {"session_id": st.session_state["thread_id"], "input_text": user_input},
    )
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        try:
            inputs = {
                "input_text": user_input,
                "resume_text": st.session_state["extracted_resume_text"],
                "jd_text": jd_input.strip(),
                "intent": "",
                "reply": "",
                "history": st.session_state.messages,
            }
            config = {"configurable": {"thread_id": st.session_state["thread_id"]}}
            output = agent_app.invoke(inputs, config)
            full_response = output.get("reply") or "抱歉，系统未能生成有效回复。"
            render_stream(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            write_audit_event(
                "chat.assistant_message",
                {
                    "session_id": st.session_state["thread_id"],
                    "intent": output.get("intent", ""),
                    "reply_preview": full_response[:500],
                },
            )
        except Exception as exc:
            write_audit_event(
                "chat.error",
                {"session_id": st.session_state["thread_id"], "error": str(exc)},
            )
            st.error(f"运行发生错误：{exc}")
