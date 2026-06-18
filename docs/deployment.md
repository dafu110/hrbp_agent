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
- `GET /me`
- `POST /chat`
- `GET /interviews`

If `ACCESS_PASSWORD` is configured, pass it as the `X-Access-Password` header.

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
- Prefer `sha256:<hash>` access passwords for shared demos; plain text remains supported for local convenience.
- Keep `.env` outside source control.
- Persist `.runtime` and `.chroma`.
- Rotate audit logs.
- Use `TOOL_EXECUTION_MODE=live` with SMTP settings only in controlled environments.
- Replace local calendar artifacts and the file-based ATS adapter with enterprise calendar and ATS APIs when credentials are available.
