# AI-Native 智能人事大管家 & HRBP Agent

一个面向企业 HRBP 场景的 AI Agent 项目，基于 Streamlit + LangGraph + LangChain 构建，支持企业制度 RAG 问答、候选人简历与 JD 匹配评估、上下文感知意图路由，以及可扩展的行政动作 Tool Calling。

## 核心能力

- 企业制度问答：从 `data/员工手册测试版.pdf` 检索制度片段，并在回答中附上页码来源。
- 简历评估：上传 PDF 简历，粘贴岗位 JD，输出结构化匹配分、优势和风险项。
- 上下文感知路由：LangGraph 负责识别 RAG、简历评估、行政动作三类任务。
- 工具调用示例：内置“发送面试邀约”模拟工具，后续可替换为邮件、ATS、日历等真实系统。
- 降级策略：模型路由失败时会回退到关键词路由，避免单点不可用导致主流程中断。

## 技术亮点

- 状态机工作流编排：基于 `StateGraph` 构建节点流转、条件路由与终点闭环。
- RAG 引用溯源：使用 Chroma + HuggingFace Embeddings 检索企业制度，并基于 PDF metadata 输出页码来源。
- 全栈数据流：Streamlit 侧边栏上传 PDF 后实时解析文本，并将简历、JD、对话输入分别注入 Agent 状态。
- Tool Calling 闭环：大模型根据语义判断是否触发行政动作工具。
- 工程化配置：模型、Embedding、知识库路径、RAG 切片参数均可通过 `.env` 管理。

## 项目结构

```text
.
├── app.py                 # Streamlit 前端入口
├── core/
│   ├── config.py          # 环境配置与模型客户端工厂
│   ├── matcher.py         # 简历/JD 结构化匹配评估
│   ├── pdf_utils.py       # PDF 文本提取工具
│   ├── rag_engine.py      # 企业制度 RAG 检索与生成
│   └── workflow.py        # LangGraph Agent 状态机
├── data/                  # 本地知识库和测试资料
├── tests/                 # 轻量单元测试
├── .env.example           # 环境变量模板
└── requirements.txt
```

## 快速开始

1. 创建并启用虚拟环境。

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

2. 安装依赖。

```powershell
pip install -r requirements.txt
```

3. 配置环境变量。

复制 `.env.example` 为 `.env`，填写兼容 OpenAI SDK 的模型网关地址与密钥。

```powershell
Copy-Item .env.example .env
```

4. 启动应用。

```powershell
python -m streamlit run app.py
```

启动成功后访问 `http://localhost:8501`。

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `OPENAI_API_KEY` | 无 | 模型 API Key |
| `OPENAI_API_BASE` | 无 | 兼容 OpenAI SDK 的 Base URL |
| `OPENAI_MODEL` | `deepseek-chat` | Chat 模型名称 |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | RAG 向量模型 |
| `HR_POLICY_PDF` | `data/员工手册测试版.pdf` | 企业制度知识库 PDF |
| `RAG_CHUNK_SIZE` | `400` | RAG 切片大小 |
| `RAG_CHUNK_OVERLAP` | `40` | RAG 切片重叠 |
| `RAG_TOP_K` | `3` | 检索片段数量 |

## 验证

```powershell
python -m py_compile app.py core\config.py core\pdf_utils.py core\workflow.py core\rag_engine.py core\matcher.py
python -m unittest discover -s tests
```

## 测试场景

- RAG 规章问答：询问“我下周去北京出差，住宿和餐饮能报销多少钱？”
- 简历评估：左侧上传 PDF 简历并粘贴 JD，输入“帮我评估一下这份简历”。
- 多轮追问：继续输入“那如果他自学过半年的 React 和前端开发呢？”
- Tool Calling：输入“帮我给张伟发送明天下午两点的面试邀约”。

## 后续扩展

- 将模拟邮件工具替换为企业邮箱、飞书/钉钉、ATS 或日历 API。
- 将 Chroma 从内存向量库切换为持久化目录或独立向量数据库。
- 为候选人评估增加评分 rubrics、面试题推荐和风险证据引用。
- 加入鉴权、审计日志、敏感信息脱敏和 Prompt/Response 追踪。
