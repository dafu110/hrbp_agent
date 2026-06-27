# PeopleOps Agent Platform

PeopleOps Agent Platform is an AI-native HRBP workbench for policy Q&A, resume/JD matching, interview actions, approvals, audit evidence, and local ATS-style records. It is designed as a practical reference project rather than a single-purpose RAG demo.

The Streamlit workbench now follows an orange operations-console visual system and a closed-loop workflow:

```text
Assemble context -> Agent judgment -> Execute action -> Governance evidence
```

![PeopleOps orange closed-loop workbench](docs/screenshots/peopleops-workbench-orange.png)

## Product Experience

The app is organized around the daily flow of an HR operator.

- **Assemble context**: upload candidate resumes, paste the JD, preview extracted resume text, and check runtime readiness.
- **Agent judgment**: route questions to policy RAG, resume/JD matching, or action tools through the LangGraph workflow.
- **Execute action**: create local interview actions, email drafts, calendar artifacts, approval requests, and ATS sync payloads.
- **Governance evidence**: review recent actions, pending approvals, audit events, connector readiness, and audit-chain integrity.

The UI uses a consistent orange palette, compact status pills, workflow cards, a closed-loop rail, operational metrics, and ledger-style evidence rows so the first screen explains both the product and the control model.

## Core Capabilities

- AI agent workflow in `core/workflow.py` with intent routing for RAG, resume analysis, and tool execution.
- Enterprise policy retrieval in `core/rag_engine.py` with persistent Chroma indexing and page-aware citations.
- Resume/JD matching in `core/matcher.py` with structured `score`, `pros`, and `cons` output.
- Local tool execution in `core/tools.py` for interview scheduling, email drafts, calendar `.ics` files, ATS exports, and approval gates.
- SQLite persistence in `core/database.py` for users, interview actions, approval requests, tenant scope, and RAG eval metrics.
- Security and governance foundations: access password support, roles, tenant headers, PII redaction, hash-chained audit logs, and audit integrity checks.
- FastAPI control plane in `api.py` for health, readiness, identity, chat, interviews, approvals, connectors, and audit endpoints.
- Deployment assets: `Dockerfile`, `docker-compose.yml`, `.devcontainer`, and deployment notes under `docs/`.

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

## Project Map

| Path | Purpose |
| --- | --- |
| `app.py` | Streamlit workbench and orange closed-loop UI. |
| `api.py` | FastAPI control plane for chat, identity, readiness, interviews, approvals, connectors, and audit data. |
| `core/` | Agent workflow, RAG, matcher, security, audit, tenancy, database, connectors, and tool execution modules. |
| `data/` | Sample HR policy, resume, and JD documents used by the demo. |
| `docs/` | Deployment notes, clean-install notes, AI coding workflow notes, and product screenshots. |
| `evals/` | RAG evaluation dataset. |
| `scripts/` | Utility scripts for password hashing and RAG evaluation. |
| `tests/` | Unit tests for core behavior, API control plane, security, tenancy, and evaluation helpers. |

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

## Enterprise Controls

- Set `ENTERPRISE_MODE=true` and `REQUIRE_ACCESS_PASSWORD=true` before exposing the API beyond a local demo.
- Store `ACCESS_PASSWORD` as `pbkdf2_sha256$...`; plain text and legacy `sha256:` values are accepted for compatibility but reported in readiness warnings.
- Generate a password hash with `python scripts/hash_password.py`, then paste the output into `.env` as `ACCESS_PASSWORD`.
- Use `TOOL_EXECUTION_MODE=approval` when interview scheduling should create an auditable pending action instead of immediately generating email, calendar, or ATS artifacts.
- Use `X-Tenant-ID`, `X-Org-ID`, and `X-Department-ID` on API calls to isolate interviews, approvals, audit context, and downstream ATS payloads.
- Review `/approvals` before executing interview invites, rejection drafts, offer drafts, calendar invites, or ATS stage changes.
- Review `/connectors` to see which enterprise HRIS, ATS, collaboration, mail, and calendar integrations are configured or still planned.
- Use `/audit/events` for recent audit inspection; each record includes a request ID and a hash-chain pointer to make accidental tampering visible.
- Use `/audit/integrity` to verify the audit hash chain before exporting evidence or closing an incident review.
- Treat SQLite, local files, and local Chroma as a reference implementation. For production, move state to PostgreSQL, object storage, and a managed vector/search service with tenant isolation.

## Docker

```powershell
docker compose up --build
```

## Repository Housekeeping

- The README references the current orange workbench screenshot at `docs/screenshots/peopleops-workbench-orange.png`.
- Older walkthrough screenshots were removed after the UI refresh to avoid documenting stale visuals.
- Python cache directories such as `__pycache__/` are ignored and should not be committed.
- No duplicate project files were found outside Git metadata and generated caches during the latest cleanup pass.
