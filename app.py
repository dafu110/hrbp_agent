import time
from uuid import uuid4

import streamlit as st

from core.config import get_settings
from core.pdf_utils import extract_pdf_text
from core.workflow import agent_app


st.set_page_config(page_title="AI HRBP Agent", page_icon="💼", layout="wide")
st.title("💼 AI HRBP Agent")


@st.cache_data(show_spinner=False)
def cached_extract_pdf_text(file_bytes: bytes) -> str:
    return extract_pdf_text(file_bytes)


def init_state() -> None:
    st.session_state.setdefault("extracted_resume_text", "")
    st.session_state.setdefault("thread_id", f"hr_session_{uuid4().hex[:8]}")
    st.session_state.setdefault(
        "messages",
        [
            {
                "role": "assistant",
                "content": (
                    "您好，我是智能 HRBP 助手。您可以上传候选人简历并粘贴 JD 做匹配评估，"
                    "也可以直接询问员工手册、考勤、报销、福利等制度问题。"
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


init_state()
settings = get_settings()

with st.sidebar:
    st.header("招聘输入")
    uploaded_resume = st.file_uploader("上传候选人简历（PDF）", type=["pdf"])

    if uploaded_resume is not None:
        try:
            with st.spinner("正在提取简历文本..."):
                text_content = cached_extract_pdf_text(uploaded_resume.getvalue())
            st.session_state["extracted_resume_text"] = text_content
            if text_content:
                st.success("简历文本提取成功")
            else:
                st.warning("PDF 未提取到可用文本，可能是扫描件或图片型简历。")
        except Exception as exc:
            st.session_state["extracted_resume_text"] = ""
            st.error(f"简历解析失败：{exc}")
    else:
        st.session_state["extracted_resume_text"] = ""

    jd_input = st.text_area(
        "岗位描述（JD）",
        height=260,
        placeholder="粘贴岗位职责、任职要求、技术栈、年限要求等信息...",
    )

    st.divider()
    st.caption(f"知识库：{settings.policy_pdf_path.name}")
    if not settings.policy_pdf_path.exists():
        st.warning("未找到企业知识库 PDF，请检查 HR_POLICY_PDF 配置。")
    if not settings.has_llm_config:
        st.warning("未配置 OPENAI_API_KEY 或 OPENAI_API_BASE，系统将只能使用部分降级能力。")


for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


if user_input := st.chat_input("请输入 HR 问题、制度问题或候选人评估需求..."):
    st.session_state.messages.append({"role": "user", "content": user_input})
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
        except Exception as exc:
            st.error(f"运行发生错误：{exc}")
