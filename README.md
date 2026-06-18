# PeopleOps Agent Platform

PeopleOps Agent Platform is an engineering-first HRBP Agent reference project for AI-native HCM scenarios. It goes beyond a RAG demo: the app now includes persistent retrieval, a LangGraph workflow, resume/JD matching, local ATS records, email draft generation, calendar artifacts, access control, audit logs, PII redaction, a FastAPI backend, Docker deployment files, and RAG evaluation scripts.

## What It Demonstrates

- AI Agent workflow: `core/workflow.py` routes requests to RAG, resume matching, or tools.
- Enterprise policy RAG: `core/rag_engine.py` uses persistent Chroma and page citations.
- Resume/JD matching: `core/matcher.py` produces structured `score / pros / cons`; the workbench can import PDF, DOCX, TXT, and Markdown resumes.
- Real local tool execution: `core/tools.py` writes ATS records to SQLite, creates `.eml` email drafts, creates `.ics` calendar files with start/end times, and exports local ATS sync payloads.
- User and role foundation: `core/auth.py` defines principals, roles, and permissions.
- Database foundation: `core/database.py` manages SQLite tables for users, interview actions, and RAG evals.
- Security and governance: `core/security.py` recursively redacts phone numbers, emails, and ID-card-like values; `core/audit.py` writes JSONL audit logs.
- SaaS-ready backend: `api.py` exposes health, identity, chat, and interview endpoints.
- Deployment: `Dockerfile`, `docker-compose.yml`, and `docs/deployment.md`.
- AI coding transparency: `docs/ai-coding-workflow.md`.
- Professional HR workbench: `app.py` includes runtime metrics, resume preview, and RAG citation preview.

## Architecture

```text
Streamlit Workbench / FastAPI
        ↓
LangGraph workflow
  ├─ intent router
  ├─ policy RAG node
  ├─ resume matcher node
  └─ tool execution node
        ↓
Engineering services
  ├─ SQLite app database
  ├─ persistent Chroma index + manifest invalidation
  ├─ audit JSONL
  ├─ PII redaction
  ├─ local ATS records
  ├─ email draft artifacts
  └─ calendar ICS artifacts
```

## Quick Start

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python -m streamlit run app.py
```

Open `http://localhost:8501`.

## API Backend

```powershell
python -m uvicorn api:app --host 0.0.0.0 --port 8000
```

Endpoints:

- `GET /health`
- `GET /me`
- `POST /chat`
- `GET /interviews`

When `ACCESS_PASSWORD` is configured, pass `X-Access-Password`.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_NAME` | `PeopleOps Agent Platform` | Product name |
| `OPENAI_API_KEY` | empty | Model API key |
| `OPENAI_API_BASE` | empty | OpenAI-compatible base URL |
| `OPENAI_MODEL` | `deepseek-chat` | Chat model |
| `EMBEDDING_MODEL` | `BAAI/bge-small-zh-v1.5` | Chinese-friendly embedding model |
| `HR_POLICY_PDF` | `data/员工手册测试版.pdf` | Policy knowledge base |
| `CHROMA_PERSIST_DIR` | `.chroma/policy` | Persistent vector index |
| `RAG_MANIFEST_PATH` | `.chroma/policy/manifest.json` | RAG index manifest |
| `APP_DB_PATH` | `.runtime/peopleops.sqlite3` | SQLite app database |
| `AUDIT_LOG_PATH` | `.runtime/audit/events.jsonl` | JSONL audit log |
| `AUDIT_LOG_MAX_BYTES` | `5000000` | Audit log rotation threshold |
| `EMAIL_DRAFT_DIR` | `.runtime/email_drafts` | Generated `.eml` drafts |
| `CALENDAR_DIR` | `.runtime/calendar` | Generated `.ics` files |
| `ATS_EXPORT_DIR` | `.runtime/ats_exports` | Local ATS sync payloads |
| `ACCESS_PASSWORD` | empty | Optional access password |
| `TOOL_EXECUTION_MODE` | `local` | `dry_run` or `local` |
| `SMTP_HOST` | empty | SMTP host used only in `live` tool mode |
| `SMTP_FROM` | `hr@example.com` | Sender for interview invitation email |

## Validation

```powershell
python -m py_compile app.py api.py core\config.py core\auth.py core\database.py core\security.py core\audit.py core\tools.py core\pdf_utils.py core\workflow.py core\rag_engine.py core\matcher.py
python -m unittest discover -s tests
```

RAG evaluation:

```powershell
python scripts\evaluate_rag.py
```

The RAG evaluator reports keyword coverage, citation count, and retrieved context size for each case.

## Docker

```powershell
docker compose up --build
```

## Interview Positioning

This project is suitable for an AI Engineer Agent role because it demonstrates:

- Python-based AI application development.
- LLM/RAG/Agent workflow implementation.
- AI Native HR product thinking.
- Tool calling that creates real local business artifacts.
- Engineering maturity: persistence, audit, redaction, tests, API, and deployment docs.
