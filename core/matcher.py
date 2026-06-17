from typing import Any, Dict, List

from langchain_core.output_parsers import SimpleJsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from .config import get_chat_model


DEFAULT_ANALYSIS = {
    "score": 0,
    "pros": ["系统暂未生成有效优势分析"],
    "cons": ["请检查模型配置、JD 与简历文本后重试"],
}


def _as_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value:
        return [str(value).strip()]
    return []


def normalize_analysis(raw: Dict[str, Any]) -> Dict[str, Any]:
    try:
        score = int(raw.get("score", 0))
    except (TypeError, ValueError):
        score = 0

    return {
        "score": max(0, min(100, score)),
        "pros": _as_list(raw.get("pros")) or DEFAULT_ANALYSIS["pros"],
        "cons": _as_list(raw.get("cons")) or DEFAULT_ANALYSIS["cons"],
    }


def analyze_resume(resume_text: str, jd_text: str) -> dict:
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """你是一个严谨、客观的资深 HRBP 与招聘顾问。
请对比【候选人简历】和【职位描述 JD】，输出可直接给招聘负责人阅读的结构化评估。

要求：
1. 只输出标准 JSON 对象，不要 Markdown，不要解释性前后缀。
2. score 必须是 0-100 的整数。
3. pros 和 cons 必须是字符串数组，每项具体、可验证，避免空泛评价。
4. 如果信息不足，要在 cons 中指出缺失信息，而不是编造经历。

JSON 字段：
- score: 匹配度整数分数。
- pros: 高匹配优势数组。
- cons: 风险、短板或待确认问题数组。
""",
            ),
            ("user", "【职位描述 JD】\n{jd}\n\n【候选人简历】\n{resume}"),
        ]
    )

    try:
        llm = get_chat_model(temperature=0.2)
        chain = prompt | llm | SimpleJsonOutputParser()
        return normalize_analysis(chain.invoke({"jd": jd_text, "resume": resume_text}))
    except Exception as exc:
        return {
            "score": 0,
            "pros": ["系统解析失败，尚未形成可信优势结论"],
            "cons": [f"模型调用或 JSON 解析失败：{exc}"],
        }
