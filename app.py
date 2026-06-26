import time
from uuid import uuid4

import streamlit as st

from core.audit import read_audit_events, verify_audit_integrity, write_audit_event
from core.config import enterprise_warnings, get_settings
from core.connectors import connector_inventory
from core.database import init_db, list_approval_requests, list_interview_actions
from core.pdf_utils import extract_document_text
from core.security import stable_hash, verify_password


settings = get_settings()
init_db()

st.set_page_config(page_title=settings.app_name, page_icon="P", layout="wide")
st.markdown(
    """
    <style>
    :root {
        --po-ink: #17201a;
        --po-muted: #66736b;
        --po-line: #d9e2da;
        --po-paper: #fbfaf4;
        --po-panel: #ffffff;
        --po-green: #1f6f4a;
        --po-blue: #255c99;
        --po-amber: #a96f18;
        --po-red: #a33a3a;
        --po-shadow: 0 18px 42px rgba(33, 43, 36, 0.08);
        --po-radius: 8px;
    }

    .stApp {
        background:
            linear-gradient(90deg, rgba(23,32,26,0.035) 1px, transparent 1px),
            linear-gradient(180deg, rgba(23,32,26,0.035) 1px, transparent 1px),
            var(--po-paper);
        background-size: 28px 28px;
        color: var(--po-ink);
    }
    .block-container {
        max-width: 1320px;
        padding-top: 1.25rem;
        padding-bottom: 2.25rem;
    }
    section[data-testid="stSidebar"] {
        background: #f2f0e7;
        border-right: 1px solid var(--po-line);
    }
    section[data-testid="stSidebar"] > div {
        padding-top: 1.25rem;
    }
    h1, h2, h3 {
        letter-spacing: 0;
        color: var(--po-ink);
    }
    div[data-testid="stMetric"] {
        background: rgba(255,255,255,0.94);
        border: 1px solid var(--po-line);
        border-radius: var(--po-radius);
        padding: 14px 16px;
        box-shadow: 0 8px 20px rgba(33, 43, 36, 0.045);
    }
    div[data-testid="stMetric"] label {
        color: var(--po-muted);
        font-size: 0.76rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: var(--po-ink);
        font-weight: 760;
    }
    .po-topline {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 18px;
        padding: 18px 20px;
        margin-bottom: 18px;
        border: 1px solid var(--po-line);
        border-radius: var(--po-radius);
        background: rgba(255,255,255,0.88);
        box-shadow: var(--po-shadow);
    }
    .po-kicker {
        color: var(--po-green);
        font-size: 12px;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.11em;
        margin-bottom: 6px;
    }
    .po-title {
        margin: 0;
        font-size: clamp(28px, 4vw, 46px);
        line-height: 1;
        font-weight: 860;
    }
    .po-subtitle {
        margin-top: 10px;
        max-width: 760px;
        color: var(--po-muted);
        font-size: 15px;
    }
    .po-status-stack {
        display: grid;
        gap: 8px;
        min-width: 210px;
    }
    .po-pill {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-height: 34px;
        padding: 7px 12px;
        border-radius: 999px;
        border: 1px solid var(--po-line);
        background: #fff;
        color: var(--po-ink);
        font-size: 12px;
        font-weight: 760;
        white-space: nowrap;
    }
    .po-pill.green { color: var(--po-green); border-color: rgba(31,111,74,0.32); background: #edf8f1; }
    .po-pill.amber { color: var(--po-amber); border-color: rgba(169,111,24,0.32); background: #fff6e6; }
    .po-pill.blue { color: var(--po-blue); border-color: rgba(37,92,153,0.30); background: #eef5ff; }
    .po-section {
        margin: 18px 0 10px;
        color: var(--po-muted);
        font-size: 12px;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }
    .po-panel {
        border: 1px solid var(--po-line);
        border-radius: var(--po-radius);
        background: rgba(255,255,255,0.9);
        padding: 16px;
        box-shadow: 0 10px 26px rgba(33, 43, 36, 0.05);
    }
    .po-panel-title {
        margin: 0 0 6px;
        color: var(--po-ink);
        font-weight: 820;
        font-size: 17px;
    }
    .po-panel-copy {
        margin: 0;
        color: var(--po-muted);
        font-size: 13px;
    }
    .po-ledger-row {
        display: grid;
        grid-template-columns: 72px minmax(0, 1fr);
        gap: 10px;
        padding: 9px 0;
        border-bottom: 1px solid rgba(217,226,218,0.74);
        font-size: 13px;
    }
    .po-ledger-row:last-child { border-bottom: 0; }
    .po-ledger-key { color: var(--po-muted); font-weight: 760; }
    .po-ledger-value { color: var(--po-ink); overflow-wrap: anywhere; }
    .po-empty {
        padding: 14px;
        border: 1px dashed var(--po-line);
        border-radius: var(--po-radius);
        color: var(--po-muted);
        background: rgba(255,255,255,0.58);
        font-size: 13px;
    }
    .stChatMessage {
        border: 1px solid rgba(217,226,218,0.72);
        border-radius: var(--po-radius);
        background: rgba(255,255,255,0.86);
    }
    .stTextInput input, .stTextArea textarea {
        border-radius: var(--po-radius);
        border-color: var(--po-line);
    }
    .stButton button {
        border-radius: var(--po-radius);
        font-weight: 760;
    }
    [data-testid="stDeployButton"] {
        display: none;
    }
    @media (max-width: 820px) {
        .po-topline {
            align-items: flex-start;
            flex-direction: column;
        }
        .po-status-stack {
            width: 100%;
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def cached_extract_document_text(file_bytes: bytes, filename: str) -> str:
    return extract_document_text(file_bytes, filename)


def get_agent_app():
    try:
        from core.workflow import agent_app
    except ModuleNotFoundError as exc:
        st.warning(f"Agent runtime dependency is not installed: {exc.name}")
        return None
    return agent_app


def get_policy_evidence(question: str) -> list[dict]:
    try:
        from core.rag_engine import retrieve_policy_evidence
    except ModuleNotFoundError as exc:
        st.warning(f"RAG runtime dependency is not installed: {exc.name}")
        return []
    return retrieve_policy_evidence(question)


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
                    "你好，我是 PeopleOps Agent。你可以上传候选人简历并粘贴 JD 做匹配评估，"
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


def pill(label: str, tone: str = "blue") -> str:
    return f'<span class="po-pill {tone}">{label}</span>'


def render_topline() -> None:
    warnings = enterprise_warnings(settings)
    access_tone = "green" if settings.access_password else "amber"
    llm_tone = "green" if settings.has_llm_config else "amber"
    readiness_tone = "green" if not warnings else "amber"
    st.markdown(
        f"""
        <div class="po-topline">
          <div>
            <div class="po-kicker">HRBP Operations Console</div>
            <h1 class="po-title">{settings.app_name}</h1>
            <div class="po-subtitle">
              面向企业内部 PeopleOps 的 AI 工作台：把政策问答、候选人匹配、面试动作、审批留痕和审计证据放在同一个操作面。
            </div>
          </div>
          <div class="po-status-stack">
            {pill("Access " + ("Controlled" if settings.access_password else "Local Demo"), access_tone)}
            {pill("LLM " + ("Configured" if settings.has_llm_config else "Degraded"), llm_tone)}
            {pill("Mode " + settings.tool_execution_mode.upper(), "blue")}
            {pill("Readiness " + ("Clear" if not warnings else "Review"), readiness_tone)}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def require_access() -> None:
    if st.session_state.get("authenticated"):
        return

    st.markdown(
        """
        <div class="po-panel">
          <div class="po-panel-title">受控访问</div>
          <p class="po-panel-copy">请输入访问口令进入 PeopleOps Agent Platform。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    password = st.text_input("访问口令", type="password")
    if st.button("进入工作台", type="primary"):
        if verify_password(password, settings.access_password):
            st.session_state["authenticated"] = True
            write_audit_event("auth.login_success", {"session_id": st.session_state["thread_id"]})
            st.rerun()
        write_audit_event("auth.login_failed", {"session_id": st.session_state["thread_id"]})
        st.error("访问口令不正确。")
    st.stop()


def render_sidebar() -> str:
    with st.sidebar:
        st.markdown('<div class="po-section">Candidate Inputs</div>', unsafe_allow_html=True)
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
            "岗位描述 JD",
            height=230,
            placeholder="粘贴岗位职责、任职要求、技能栈、年限要求等信息...",
        )

        if st.session_state["extracted_resume_text"]:
            with st.expander("简历文本预览", expanded=False):
                st.text(st.session_state["extracted_resume_text"][:3000])

        st.markdown('<div class="po-section">Retrieval Preview</div>', unsafe_allow_html=True)
        preview_question = st.text_input("检索问题", placeholder="例如：出差报销有什么标准？")
        if st.button("预览引用", use_container_width=True) and preview_question.strip():
            evidence = get_policy_evidence(preview_question.strip())
            if evidence:
                for item in evidence:
                    st.caption(item["source"])
                    st.write(item["snippet"])
            else:
                st.warning("未检索到引用片段。")

        st.markdown('<div class="po-section">Runtime Signals</div>', unsafe_allow_html=True)
        if not settings.policy_pdf_path.exists():
            st.warning("未找到企业知识库 PDF，请检查 HR_POLICY_PDF 配置。")
        if not settings.has_llm_config:
            st.warning("未配置 OPENAI_API_KEY 或 OPENAI_API_BASE，系统将只能使用部分降级能力。")
        if settings.access_password:
            st.success("访问控制已开启")
        else:
            st.warning("访问控制未开启，可配置 ACCESS_PASSWORD。")
        return jd_input


def render_metrics() -> None:
    interviews = list_interview_actions(limit=100)
    approvals = list_approval_requests(limit=100)
    integrity = verify_audit_integrity()
    connectors = connector_inventory()
    configured_connectors = [item for item in connectors if item["status"] == "configured"]
    session_short_id = st.session_state["thread_id"].replace("peopleops_session_", "")

    cols = st.columns(5)
    with cols[0]:
        st.metric("会话", session_short_id)
    with cols[1]:
        st.metric("简历文件", len(st.session_state["resume_file_names"]))
    with cols[2]:
        st.metric("面试动作", len(interviews))
    with cols[3]:
        st.metric("待审请求", len([item for item in approvals if item["status"] == "PENDING"]))
    with cols[4]:
        st.metric("审计链", "Valid" if integrity.get("valid") else "Review")

    st.markdown(
        f"""
        <div class="po-panel">
          <div class="po-panel-title">Enterprise posture</div>
          <p class="po-panel-copy">
            Tenant: {settings.default_tenant_id} · DB: {settings.database_backend} · Vector: {settings.vector_backend} ·
            Connectors configured: {len(configured_connectors)}/{len(connectors)}
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_activity_panel() -> None:
    action_col, approval_col, audit_col = st.columns(3)
    with action_col:
        st.markdown('<div class="po-section">Recent Actions</div>', unsafe_allow_html=True)
        actions = list_interview_actions(limit=5)
        if actions:
            for action in actions:
                st.markdown(
                    f"""
                    <div class="po-ledger-row">
                      <div class="po-ledger-key">#{action['id']}</div>
                      <div class="po-ledger-value">{action['status']} · {action['candidate_name']} · {action['interview_time']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.markdown('<div class="po-empty">暂无面试动作。</div>', unsafe_allow_html=True)

    with approval_col:
        st.markdown('<div class="po-section">Approval Queue</div>', unsafe_allow_html=True)
        approvals = list_approval_requests(limit=5)
        if approvals:
            for approval in approvals:
                st.markdown(
                    f"""
                    <div class="po-ledger-row">
                      <div class="po-ledger-key">#{approval['id']}</div>
                      <div class="po-ledger-value">{approval['status']} · {approval['action_type']} · {approval['subject_ref']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.markdown('<div class="po-empty">暂无待处理审批。</div>', unsafe_allow_html=True)

    with audit_col:
        st.markdown('<div class="po-section">Audit Trail</div>', unsafe_allow_html=True)
        events = read_audit_events(limit=5)
        if events:
            for event in reversed(events):
                st.markdown(
                    f"""
                    <div class="po-ledger-row">
                      <div class="po-ledger-key">{event.get('event_type', 'event')}</div>
                      <div class="po-ledger-value">{event.get('timestamp', '')[:19]} · {event.get('actor') or 'local'}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.markdown('<div class="po-empty">暂无审计事件。</div>', unsafe_allow_html=True)


def render_chat(jd_input: str) -> None:
    st.markdown('<div class="po-section">Agent Workspace</div>', unsafe_allow_html=True)
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
                runtime = get_agent_app()
                if runtime is None:
                    raise RuntimeError("Agent runtime dependency is unavailable. Install requirements.txt to enable chat.")
                inputs = {
                    "input_text": user_input,
                    "resume_text": st.session_state["extracted_resume_text"],
                    "jd_text": jd_input.strip(),
                    "intent": "",
                    "reply": "",
                    "history": st.session_state.messages,
                }
                config = {"configurable": {"thread_id": st.session_state["thread_id"]}}
                output = runtime.invoke(inputs, config)
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


init_state()
require_access()
render_topline()
jd_text = render_sidebar()
render_metrics()

tabs = st.tabs(["Agent Console", "Governance Evidence"])
with tabs[0]:
    render_chat(jd_text)
with tabs[1]:
    render_activity_panel()
