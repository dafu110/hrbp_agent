# Deployment

## Local Streamlit

```powershell
python -m streamlit run app.py
```

## Local API

```powershell
python -m uvicorn api:app --host 0.0.0.0 --port 8000
```

Useful endpoints:

- `GET /health`
- `GET /readiness`
- `GET /enterprise/scorecard`
- `GET /me`
- `POST /chat`
- `GET /interviews`
- `GET /approvals`
- `GET /connectors`

If `ACCESS_PASSWORD` is configured, pass it as the `X-Access-Password` header.
Pass `X-Tenant-ID`, `X-Org-ID`, and `X-Department-ID` from your API gateway or identity layer so every ATS action, approval, and audit event carries a tenant boundary.

## Docker

```powershell
docker compose up --build
```

Runtime state is mounted into:

- `.runtime/peopleops.sqlite3`
- `.runtime/audit/events.jsonl`
- `.runtime/email_drafts/`
- `.runtime/calendar/`
- `.runtime/ats_exports/`
- `.chroma/policy/`

## Production Checklist

- Configure `ACCESS_PASSWORD`.
- Prefer `pbkdf2_sha256$...` access passwords for shared demos; plain text remains supported for local convenience and is reported as a readiness warning.
- Keep `.env` outside source control.
- Replace SQLite with PostgreSQL and set `DATABASE_BACKEND=postgresql` once the production adapter is wired.
- Replace local Chroma with pgvector, Qdrant, Milvus, Elasticsearch/OpenSearch, or a managed vector/search service and set `VECTOR_BACKEND` accordingly.
- Move resumes, JD files, generated artifacts, and audit exports to S3, MinIO, OSS, or managed object storage via `OBJECT_STORAGE_URI`.
- Set real `DEFAULT_TENANT_ID`, `DEFAULT_ORG_ID`, and `DEFAULT_DEPARTMENT_ID`; do not use `default` in enterprise mode.
- Keep `TOOL_EXECUTION_MODE=approval` for interview invites, rejection drafts, offer drafts, calendar invites, and ATS stage changes until an HR reviewer approves `/approvals` entries.
- Use `/connectors` to track Workday, BambooHR, Greenhouse, Lever, Feishu, DingTalk, Enterprise WeChat, Outlook, and Google Calendar readiness.
- Persist `.runtime` and `.chroma` only for local reference deployments.
- Rotate audit logs.
- Use `TOOL_EXECUTION_MODE=live` with SMTP settings only in controlled environments.
- Replace local calendar artifacts and the file-based ATS adapter with enterprise calendar and ATS APIs when credentials are available.
