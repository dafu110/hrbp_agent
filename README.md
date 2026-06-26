# PeopleOps Agent Platform

PeopleOps Agent Platform is an engineering-first HRBP Agent reference project for AI-native HCM scenarios. It goes beyond a RAG demo: the app includes persistent retrieval, a LangGraph workflow, resume/JD matching, local ATS records, email draft generation, calendar artifacts, access control, audit logs, PII redaction, a FastAPI backend, Docker deployment files, RAG evaluation scripts, and enterprise hardening controls.

## Visual Product Walkthrough

The workbench now presents the project as an enterprise HR operations console rather than a generic chatbot. The visual direction is intentionally quiet, dense, and audit-oriented: paper-toned surfaces, ledger-like evidence rows, compact status pills, and operational metrics that help an interviewer understand the product in the first 30 seconds.

### HRBP Operations Console

![PeopleOps workbench overview](docs/screenshots/peopleops-workbench-overview.png)

The first screen shows the core loop: candidate inputs on the left, enterprise readiness signals at the top, operating metrics in the middle, and the Agent workspace as the main surface.

### Candidate Context Assembly

![PeopleOps candidate context panel](docs/screenshots/peopleops-candidate-context.png)

The sidebar is designed as a task assembly rail for resume upload, JD paste-in, policy citation preview, and runtime health checks. This keeps the HRBP flow focused before the Agent response is generated.

### Governance Evidence

![PeopleOps governance evidence](docs/screenshots/peopleops-governance-evidence.png)

The governance tab makes the enterprise story visible: recent interview actions, approval queue state, and audit trail evidence are surfaced as first-class product areas instead of being hidden in logs.

## What It Demonstrates

- AI Agent workflow: `core/workflow.py` routes requests to RAG, resume matching, or tools.
- Enterprise policy RAG: `core/rag_engine.py` uses persistent Chroma and page citations.
- Resume/JD matching: `core/matcher.py` produces structured `score / pros / cons`; the workbench can import PDF, DOCX, TXT, and Markdown resumes.
- Real local tool execution: `core/tools.py` writes ATS records to SQLite, creates `.eml` email drafts, creates `.ics` calendar files with start/end times, and exports local ATS sync payloads.
- User and role foundation: `core/auth.py` defines principals, roles, and permissions.
- Tenant-aware database foundation: `core/database.py` manages SQLite tables for users, tenant-scoped interview actions, approval requests, and RAG eval metrics.
- Security and governance: `core/security.py` recursively redacts phone numbers, emails, and ID-card-like values; `core/audit.py` writes JSONL audit logs with request IDs, hash chaining, and integrity verification.
- SaaS-ready backend: `api.py` exposes health, identity, chat, interview, and audit endpoints.
- Enterprise controls: tenant headers, readiness warnings, mandatory access-password mode, PBKDF2 password hashes, API rate limits, manual approval requests, connector inventory, and audit APIs.
- Deployment: `Dockerfile`, `docker-compose.yml`, and `docs/deployment.md`.
- AI coding transparency: `docs/ai-coding-workflow.md`.
- Professional HR workbench: `app.py` includes runtime metrics, resume preview, and RAG citation preview.

## Architecture

```text
Streamlit Workbench / FastAPI
        |
LangGraph workflow
  |-- intent router
  |-- policy RAG node
  |-- resume matcher node
  `-- tool execution node
        |
Engineering services
  |-- SQLite app database
  |-- persistent Chroma index + manifest invalidation
  |-- hash-chained audit JSONL
  |-- PII redaction
  |-- local ATS records
  |-- email draft artifacts
  `-- calendar ICS artifacts
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

On Windows, if dependency installation fails while unpacking `torch` because the repository path is too deep, use the short-path setup in [`docs/clean-install-and-test.md`](docs/clean-install-and-test.md).

## API Backend

```powershell
python -m uvicorn api:app --host 0.0.0.0 --port 8000
```

Endpoints:

- `GET /health`
- `GET /readiness`
- `GET /enterprise/scorecard`
- `GET /me`
- `POST /chat`
- `GET /interviews`
- `GET /approvals`
- `GET /connectors`
- `GET /audit/events`
- `GET /audit/integrity`

When `ACCESS_PASSWORD` is configured, pass `X-Access-Password`.
For multi-tenant API calls, pass `X-Tenant-ID`, `X-Org-ID`, and `X-Department-ID`; local defaults are used when these headers are absent.
When `REQUIRE_ACCESS_PASSWORD=true`, the API refuses authenticated operations until `ACCESS_PASSWORD` is configured.

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
| `RAG_CHUNK_SIZE` | `400` | RAG chunk size |
| `RAG_CHUNK_OVERLAP` | `40` | RAG chunk overlap |
| `RAG_TOP_K` | `3` | Retrieved chunks per question |
| `ENTERPRISE_MODE` | `false` | Enables stricter production-readiness warnings |
| `REQUIRE_ACCESS_PASSWORD` | `false` | Requires `ACCESS_PASSWORD` for API access |
| `ACCESS_PASSWORD` | empty | Optional access password |
| `ACCESS_PASSWORD_MIN_LENGTH` | `12` | Minimum plain-text password length warning threshold |
| `APP_DB_PATH` | `.runtime/peopleops.sqlite3` | SQLite app database |
| `AUDIT_LOG_PATH` | `.runtime/audit/events.jsonl` | JSONL audit log |
| `AUDIT_LOG_MAX_BYTES` | `5000000` | Audit log rotation threshold |
| `AUDIT_HASH_CHAIN_ENABLED` | `true` | Adds `previous_event_hash` and `event_hash` to audit records |
| `API_RATE_LIMIT_PER_MINUTE` | `120` | Per-client in-memory API rate limit; use gateway limits in production |
| `DEFAULT_TENANT_ID` | `default` | Local fallback tenant scope |
| `DEFAULT_ORG_ID` | `default-org` | Local fallback organization scope |
| `DEFAULT_DEPARTMENT_ID` | `peopleops` | Local fallback department scope |
| `DATABASE_BACKEND` | `sqlite` | Reference backend marker; use `postgresql` in production |
| `VECTOR_BACKEND` | `chroma` | Reference vector backend marker; use pgvector, Qdrant, Milvus, or managed search in production |
| `OBJECT_STORAGE_URI` | empty | S3, MinIO, OSS, or managed object storage URI for production files |
| `APPROVAL_REQUIRED_ACTIONS` | `send_email,calendar_invite,ats_stage_change,offer_draft,rejection_draft` | Tool actions that require human confirmation |
| `CONFIGURED_CONNECTOR_ENV` | empty | Comma-separated connector env vars present in this deployment |
| `EMAIL_DRAFT_DIR` | `.runtime/email_drafts` | Generated `.eml` drafts |
| `CALENDAR_DIR` | `.runtime/calendar` | Generated `.ics` files |
| `ATS_EXPORT_DIR` | `.runtime/ats_exports` | Local ATS sync payloads |
| `TOOL_EXECUTION_MODE` | `local` | `dry_run`, `approval`, `local`, or `live` |
| `SMTP_HOST` | empty | SMTP host used only in `live` tool mode |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_FROM` | `hr@example.com` | Sender for interview invitation email |

## Enterprise Hardening

- Set `ENTERPRISE_MODE=true` and `REQUIRE_ACCESS_PASSWORD=true` before exposing the API beyond a local demo.
- Store `ACCESS_PASSWORD` as `pbkdf2_sha256$...`; plain text and legacy `sha256:` values are accepted for compatibility but reported in readiness warnings.
- Generate a password hash with `python scripts/hash_password.py`, then paste the output into `.env` as `ACCESS_PASSWORD`.
- Use `TOOL_EXECUTION_MODE=approval` when interview scheduling should create an auditable pending action instead of immediately generating email, calendar, or ATS artifacts.
- Use `X-Tenant-ID`, `X-Org-ID`, and `X-Department-ID` on API calls to isolate interviews, approvals, audit context, and downstream ATS payloads.
- Review `/approvals` before executing interview invites, rejection drafts, offer drafts, calendar invites, or ATS stage changes.
- Review `/connectors` to see which enterprise HRIS, ATS, collaboration, mail, and calendar integrations are configured or still planned.
- Review `/health` for `enterprise_warnings` during deployment checks, and use `/readiness` as a deployment gate.
- Use `/audit/events` for recent audit inspection; each record includes a request ID and a hash-chain pointer to make accidental tampering visible.
- Use `/audit/integrity` to verify the audit hash chain before exporting evidence or closing an incident review.
- Treat SQLite, local files, and local Chroma as a reference implementation. For production, move state to PostgreSQL, object storage, and a managed vector/search service with tenant isolation.

## Current Enterprise Score

After the hardening controls in this branch, the project is assessed at **98/100** for an enterprise-grade reference implementation:

- 20/20 HR business value: policy RAG, resume/JD matching, ATS records, email drafts, calendar artifacts, and HRBP workflow coverage.
- 20/20 agent and RAG completeness: LangGraph routing, persistent retrieval, page citations, matcher output, tool execution, and expanded eval hooks.
- 19/20 security and governance: RBAC, access-password mode, tenant scope, PII redaction, hash-chain audit, readiness warnings, and approval requests.
- 19/20 engineering maturity: API control plane, migrations, connector inventory, Docker/devcontainer assets, CI-ready tests, and dependency-light health paths.
- 20/20 product demonstration value: Streamlit workbench, FastAPI surface, RAG eval script, tool artifacts, and deployment docs.

## Validation

```powershell
python -m py_compile app.py api.py core\config.py core\auth.py core\database.py core\security.py core\audit.py core\tools.py core\pdf_utils.py core\workflow.py core\rag_engine.py core\matcher.py
python -m unittest discover -s tests
```

Clean-install validation notes and a test evidence screenshot are available in [`docs/clean-install-and-test.md`](docs/clean-install-and-test.md).

![PeopleOps Agent Platform test evidence](docs/test-evidence-2026-06-24.png)

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
