from typing import Dict, List, Literal, TypedDict

from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from .config import get_chat_model
from .matcher import analyze_resume
from .rag_engine import ask_rag


Intent = Literal["action_tool", "resume", "rag"]


class AgentState(TypedDict):
    input_text: str
    resume_text: str
    jd_text: str
    intent: str
    reply: str
    history: List[Dict[str, str]]


ACTION_KEYWORDS = ["邮件", "发件", "邀约", "通知", "发通知", "录用", "安排", "面试"]
RESUME_KEYWORDS = [
    "简历",
    "匹配",
    "评估",
    "候选人",
    "jd",
    "职位",
    "react",
    "vue",
    "python",
    "前端",
    "后端",
    "开发",
    "技术",
    "能力",
    "学过",
    "自学",
    "如果他",
    "要是",
]


@tool
def send_interview_email(candidate_name: str, interview_time: str) -> str:
    """
    当用户明确要求给候选人发送面试邀约邮件、通知候选人、或者安排面试时间时，调用此工具。
    """
    return (
        f"**[系统动作]** 已模拟发送面试邀约：候选人【{candidate_name}】，"
        f"面试时间【{interview_time}】。后续可对接企业邮件、ATS 或日历系统。"
    )


def keyword_intent(text: str) -> Intent:
    text_lower = text.lower()
    if any(keyword in text_lower for keyword in ACTION_KEYWORDS):
        return "action_tool"
    if any(keyword.lower() in text_lower for keyword in RESUME_KEYWORDS):
        return "resume"
    return "rag"


def _format_history(history: List[Dict[str, str]], limit: int = 6) -> str:
    if not history:
        return "无"

    lines = []
    for msg in history[-limit:]:
        role = "用户" if msg.get("role") == "user" else "助手"
        content = str(msg.get("content", "")).strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines) if lines else "无"


def parse_intent(state: AgentState):
    text = state.get("input_text", "").strip()
    history = state.get("history", [])

    system_prompt = """你是企业智能 HR Agent 的中央意图路由器。
请根据当前用户输入与历史对话，将意图分类为以下三类之一：

action_tool: 用户要执行行政动作，例如发邮件、发面试邀约、通知候选人、安排面试、录用。
resume: 用户要评估简历、对比 JD、筛选候选人，或延续上文追问候选人的技能、风险、评分变化。
rag: 用户询问公司制度、考勤、报销、请假、福利、企业文化等知识库内容。

你必须只输出 action_tool、resume、rag 三个单词之一。"""

    user_content = f"""【历史对话】
{_format_history(history)}

【当前用户输入】
{text}

请输出分类结果："""

    try:
        llm = get_chat_model(temperature=0.0)
        response = llm.invoke([("system", system_prompt), ("user", user_content)])
        intent_result = response.content.strip().lower()

        if "action_tool" in intent_result:
            return {"intent": "action_tool"}
        if "resume" in intent_result:
            return {"intent": "resume"}
        if "rag" in intent_result:
            return {"intent": "rag"}
    except Exception as exc:
        print(f"[Router fallback] {exc}")

    return {"intent": keyword_intent(text)}


def handle_rag(state: AgentState):
    return {"reply": ask_rag(state["input_text"])}


def handle_resume(state: AgentState):
    resume_content = state.get("resume_text", "").strip()
    jd_text = state.get("jd_text", "").strip()
    user_msg = state.get("input_text", "").strip()

    if not resume_content:
        return {
            "reply": "检测到尚未上传候选人简历。请先在左侧上传 PDF 简历，再发起简历评估。"
        }

    if not jd_text:
        jd_text = user_msg

    resume_with_context = (
        f"{resume_content}\n\n"
        f"【本轮用户问题或补充条件】\n{user_msg or '无'}"
    )
    result = analyze_resume(resume_text=resume_with_context, jd_text=jd_text)

    pros = "\n".join([f"{idx}. {item}" for idx, item in enumerate(result["pros"], start=1)])
    cons = "\n".join([f"{idx}. {item}" for idx, item in enumerate(result["cons"], start=1)])

    return {
        "reply": f"""### 候选人综合评估报告

**综合匹配度：{result.get("score", 0)} / 100**

#### 核心优势
{pros}

#### 风险与待确认项
{cons}
"""
    }


def handle_action_tool(state: AgentState):
    user_msg = state["input_text"]

    try:
        llm = get_chat_model(temperature=0.0)
        llm_with_tools = llm.bind_tools([send_interview_email])
        ai_msg = llm_with_tools.invoke(
            f"用户当前说的话：{user_msg}。如果需要发面试邀约，请提取候选人姓名和面试时间并调用工具。"
        )

        if ai_msg.tool_calls:
            args = ai_msg.tool_calls[0]["args"]
            return {"reply": send_interview_email.invoke(args)}
    except Exception as exc:
        return {"reply": f"已识别到行政动作意图，但工具调用失败：{exc}"}

    return {
        "reply": "已识别到行政动作意图，但缺少候选人姓名或面试时间。请补充类似“给张伟发送明天下午两点的面试邀约”。"
    }


def router(state: AgentState):
    if state["intent"] == "action_tool":
        return "tool_node"
    if state["intent"] == "resume":
        return "resume_node"
    return "rag_node"


workflow = StateGraph(AgentState)
workflow.add_node("intent_node", parse_intent)
workflow.add_node("rag_node", handle_rag)
workflow.add_node("resume_node", handle_resume)
workflow.add_node("tool_node", handle_action_tool)

workflow.set_entry_point("intent_node")
workflow.add_conditional_edges(
    "intent_node",
    router,
    {
        "tool_node": "tool_node",
        "resume_node": "resume_node",
        "rag_node": "rag_node",
    },
)
workflow.add_edge("rag_node", END)
workflow.add_edge("resume_node", END)
workflow.add_edge("tool_node", END)

agent_app = workflow.compile(checkpointer=MemorySaver())
