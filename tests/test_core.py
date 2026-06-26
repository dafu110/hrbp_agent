import os
import importlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.audit import read_audit_events, verify_audit_integrity, write_audit_event
from core.auth import Principal, has_permission
from core.config import enterprise_warnings, get_settings
from core.database import list_approval_requests, list_interview_actions
from core.matcher import normalize_analysis
from core.pdf_utils import extract_document_text
from core.security import hash_password, redact_payload, redact_pii, verify_password
from core.tools import parse_interview_window, schedule_interview
from core.tenancy import TenantContext


class MatcherNormalizationTests(unittest.TestCase):
    def test_normalize_analysis_clamps_score_and_lists(self):
        result = normalize_analysis({"score": 120, "pros": "Python experience", "cons": ["No people management"]})

        self.assertEqual(result["score"], 100)
        self.assertEqual(result["pros"], ["Python experience"])
        self.assertEqual(result["cons"], ["No people management"])


class SecurityTests(unittest.TestCase):
    def test_redact_pii_masks_common_identifiers(self):
        text = "phone 13812345678, email test@example.com, id 110101199003071234"

        redacted = redact_pii(text)

        self.assertNotIn("13812345678", redacted)
        self.assertNotIn("test@example.com", redacted)
        self.assertNotIn("110101199003071234", redacted)
        self.assertIn("[PHONE_REDACTED]", redacted)
        self.assertIn("[EMAIL_REDACTED]", redacted)
        self.assertIn("[ID_CARD_REDACTED]", redacted)

    def test_verify_password_allows_empty_expected_password(self):
        self.assertTrue(verify_password("", None))
        self.assertTrue(verify_password("secret", "secret"))
        self.assertFalse(verify_password("wrong", "secret"))

    def test_redact_payload_masks_nested_values(self):
        payload = {"candidate": {"email": "test@example.com", "items": ["13812345678"]}}

        redacted = redact_payload(payload)

        self.assertEqual(redacted["candidate"]["email"], "[EMAIL_REDACTED]")
        self.assertEqual(redacted["candidate"]["items"][0], "[PHONE_REDACTED]")


class DocumentImportTests(unittest.TestCase):
    def test_extract_document_text_supports_plain_text(self):
        result = extract_document_text("Candidate has Python experience".encode("utf-8"), "resume.txt")

        self.assertIn("Python", result)


class IsolatedRuntimeMixin:
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self._old_env = {
            key: os.environ.get(key)
            for key in (
                "APP_DB_PATH",
                "AUDIT_LOG_PATH",
                "EMAIL_DRAFT_DIR",
                "CALENDAR_DIR",
                "ATS_EXPORT_DIR",
                "TOOL_EXECUTION_MODE",
                "ENTERPRISE_MODE",
                "REQUIRE_ACCESS_PASSWORD",
                "ACCESS_PASSWORD",
                "ACCESS_PASSWORD_MIN_LENGTH",
                "AUDIT_HASH_CHAIN_ENABLED",
                "API_RATE_LIMIT_PER_MINUTE",
                "DEFAULT_TENANT_ID",
                "DEFAULT_ORG_ID",
                "DEFAULT_DEPARTMENT_ID",
                "DATABASE_BACKEND",
                "VECTOR_BACKEND",
                "OBJECT_STORAGE_URI",
                "APPROVAL_REQUIRED_ACTIONS",
                "CONFIGURED_CONNECTOR_ENV",
            )
        }
        root = Path(self._tmpdir.name)
        os.environ["APP_DB_PATH"] = str(root / "peopleops.sqlite3")
        os.environ["AUDIT_LOG_PATH"] = str(root / "audit" / "events.jsonl")
        os.environ["EMAIL_DRAFT_DIR"] = str(root / "email_drafts")
        os.environ["CALENDAR_DIR"] = str(root / "calendar")
        os.environ["ATS_EXPORT_DIR"] = str(root / "ats_exports")
        os.environ["TOOL_EXECUTION_MODE"] = "local"
        os.environ.pop("ENTERPRISE_MODE", None)
        os.environ.pop("REQUIRE_ACCESS_PASSWORD", None)
        os.environ.pop("ACCESS_PASSWORD", None)
        os.environ.pop("ACCESS_PASSWORD_MIN_LENGTH", None)
        os.environ.pop("AUDIT_HASH_CHAIN_ENABLED", None)
        os.environ.pop("API_RATE_LIMIT_PER_MINUTE", None)
        os.environ.pop("DEFAULT_TENANT_ID", None)
        os.environ.pop("DEFAULT_ORG_ID", None)
        os.environ.pop("DEFAULT_DEPARTMENT_ID", None)
        os.environ.pop("DATABASE_BACKEND", None)
        os.environ.pop("VECTOR_BACKEND", None)
        os.environ.pop("OBJECT_STORAGE_URI", None)
        os.environ.pop("APPROVAL_REQUIRED_ACTIONS", None)
        os.environ.pop("CONFIGURED_CONNECTOR_ENV", None)
        get_settings.cache_clear()

    def tearDown(self):
        for key, value in self._old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()
        self._tmpdir.cleanup()


class ToolExecutionTests(IsolatedRuntimeMixin, unittest.TestCase):
    def test_parse_interview_window_handles_iso_time(self):
        now = datetime(2026, 6, 18, 9, 0, tzinfo=timezone(timedelta(hours=8), name="Asia/Shanghai"))

        window = parse_interview_window("2026-06-20 14:30", now=now)

        self.assertIsNotNone(window)
        self.assertEqual(window[0].strftime("%Y-%m-%d %H:%M"), "2026-06-20 14:30")
        self.assertEqual(window[1].strftime("%Y-%m-%d %H:%M"), "2026-06-20 15:30")

    def test_schedule_interview_returns_auditable_local_result(self):
        result = schedule_interview("Alice", "2026-06-20 14:00", candidate_email="candidate@example.com")

        self.assertEqual(result.tool_name, "schedule_interview")
        self.assertIn(result.status, {"DRY_RUN", "PERSISTED", "SUCCESS"})
        self.assertIn("execution_mode", result.metadata)
        self.assertGreaterEqual(len(list_interview_actions(limit=1)), 1)
        calendar_path = Path(result.metadata["calendar_event_path"])
        self.assertTrue(calendar_path.exists())
        calendar_text = calendar_path.read_text(encoding="utf-8")
        self.assertIn("DTSTART;TZID=Asia/Shanghai:20260620T140000", calendar_text)
        self.assertIn("DTEND;TZID=Asia/Shanghai:20260620T150000", calendar_text)
        self.assertTrue(Path(result.metadata["ats_export_path"]).exists())

    def test_schedule_interview_can_require_manual_approval(self):
        os.environ["TOOL_EXECUTION_MODE"] = "approval"
        get_settings.cache_clear()

        result = schedule_interview("Bob", "2026-06-21 10:00", candidate_email="bob@example.com")

        self.assertEqual(result.status, "PENDING_APPROVAL")
        self.assertEqual(result.metadata["email_draft_path"], "dry_run")
        self.assertEqual(result.metadata["calendar_event_path"], "dry_run")
        self.assertEqual(result.metadata["ats_export_path"], "dry_run")
        self.assertIsInstance(result.metadata["approval_request_id"], int)
        self.assertEqual(list_interview_actions(limit=1)[0]["status"], "PENDING_APPROVAL")
        self.assertEqual(list_approval_requests(limit=1)[0]["status"], "PENDING")

    def test_schedule_interview_records_tenant_scope(self):
        result = schedule_interview(
            "Carol",
            "2026-06-22 11:00",
            tenant_id="tenant-a",
            org_id="org-a",
            department_id="recruiting",
        )

        self.assertEqual(result.metadata["tenant_id"], "tenant-a")
        self.assertEqual(list_interview_actions(limit=5, tenant_id="tenant-a")[0]["org_id"], "org-a")
        self.assertEqual(list_interview_actions(limit=5, tenant_id="tenant-b"), [])


class AuditTests(IsolatedRuntimeMixin, unittest.TestCase):
    def test_audit_events_include_hash_chain_and_redaction(self):
        first = write_audit_event("test.first", {"email": "test@example.com"})
        second = write_audit_event("test.second", {"phone": "13812345678"})
        events = read_audit_events(limit=2)

        self.assertEqual(len(events), 2)
        self.assertTrue(first["event_hash"])
        self.assertEqual(second["previous_event_hash"], first["event_hash"])
        self.assertEqual(events[0]["payload"]["email"], "[EMAIL_REDACTED]")
        self.assertEqual(events[1]["payload"]["phone"], "[PHONE_REDACTED]")

    def test_audit_integrity_detects_tampering(self):
        write_audit_event("test.first", {"email": "test@example.com"})
        self.assertTrue(verify_audit_integrity()["valid"])

        audit_path = get_settings().audit_log_path
        events = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
        events[0]["payload"]["email"] = "tampered@example.com"
        audit_path.write_text(json.dumps(events[0], ensure_ascii=False) + "\n", encoding="utf-8")

        result = verify_audit_integrity()
        self.assertFalse(result["valid"])
        self.assertEqual(result["errors"][0]["error"], "event_hash_mismatch")


class AuthorizationTests(unittest.TestCase):
    def test_role_permissions(self):
        self.assertTrue(has_permission(Principal("alice", "admin"), "users"))
        self.assertTrue(has_permission(Principal("bob", "hrbp"), "tool"))
        self.assertFalse(has_permission(Principal("viewer", "viewer"), "tool"))


class TenancyTests(unittest.TestCase):
    def test_tenant_context_sanitizes_header_values(self):
        scope = TenantContext.from_headers(
            tenant_id=" tenant/a ",
            org_id="org@main",
            department_id="people ops",
            default_tenant_id="default",
            default_org_id="default-org",
            default_department_id="peopleops",
        )

        self.assertEqual(scope.tenant_id, "tenanta")
        self.assertEqual(scope.org_id, "orgmain")
        self.assertEqual(scope.department_id, "peopleops")


class ApiControlPlaneTests(IsolatedRuntimeMixin, unittest.TestCase):
    def test_health_and_audit_endpoints_do_not_require_agent_runtime(self):
        from fastapi.testclient import TestClient
        import api

        api = importlib.reload(api)
        with TestClient(api.app) as client:
            health = client.get("/health")
            self.assertEqual(health.status_code, 200)
            self.assertEqual(health.json()["status"], "ok")
            self.assertEqual(health.json()["database_backend"], "sqlite")

            scorecard = client.get("/enterprise/scorecard")
            self.assertEqual(scorecard.status_code, 200)
            self.assertEqual(scorecard.json()["score"], 98)

            audit = client.get("/audit/events")
            self.assertEqual(audit.status_code, 200)
            self.assertEqual(audit.json(), [])

            integrity = client.get("/audit/integrity")
            self.assertEqual(integrity.status_code, 200)
            self.assertTrue(integrity.json()["valid"])

            readiness = client.get("/readiness")
            self.assertEqual(readiness.status_code, 200)
            self.assertTrue(readiness.json()["ready"])

            connectors = client.get("/connectors")
            self.assertEqual(connectors.status_code, 200)
            self.assertGreaterEqual(len(connectors.json()["connectors"]), 5)

            me = client.get("/me", headers={"X-Tenant-ID": "tenant-a", "X-Org-ID": "org-a"})
            self.assertEqual(me.status_code, 200)
            self.assertEqual(me.json()["tenant_id"], "tenant-a")

    def test_chat_returns_service_error_when_agent_runtime_is_missing(self):
        from fastapi import HTTPException
        from fastapi.testclient import TestClient
        import api

        api = importlib.reload(api)
        original_get_agent_app = api.get_agent_app
        api.get_agent_app = lambda: (_ for _ in ()).throw(HTTPException(status_code=503, detail="Agent runtime unavailable"))
        try:
            with TestClient(api.app) as client:
                response = client.post("/chat", json={"message": "hello"})
        finally:
            api.get_agent_app = original_get_agent_app

        self.assertEqual(response.status_code, 503)

    def test_chat_request_validation_limits_empty_message(self):
        from fastapi import HTTPException
        from fastapi.testclient import TestClient
        import api

        api = importlib.reload(api)
        original_get_agent_app = api.get_agent_app
        api.get_agent_app = lambda: (_ for _ in ()).throw(HTTPException(status_code=503, detail="Agent runtime unavailable"))
        try:
            with TestClient(api.app) as client:
                response = client.post("/chat", json={"message": ""})
        finally:
            api.get_agent_app = original_get_agent_app

        self.assertEqual(response.status_code, 422)

    def test_api_rate_limit_can_be_enforced(self):
        from fastapi.testclient import TestClient
        import api

        os.environ["API_RATE_LIMIT_PER_MINUTE"] = "2"
        get_settings.cache_clear()
        api = importlib.reload(api)
        with TestClient(api.app) as client:
            self.assertEqual(client.get("/health").status_code, 200)
            self.assertEqual(client.get("/health").status_code, 200)
            self.assertEqual(client.get("/health").status_code, 429)


class PasswordHashingTests(unittest.TestCase):
    def test_pbkdf2_password_hash_roundtrip_and_legacy_support(self):
        encoded = hash_password("secret", salt="fixed-salt", iterations=1000)

        self.assertTrue(encoded.startswith("pbkdf2_sha256$1000$fixed-salt$"))
        self.assertTrue(verify_password("secret", encoded))
        self.assertFalse(verify_password("wrong", encoded))
        self.assertTrue(verify_password("secret", "sha256:2bb80d537b1da3e38bd30361aa855686bde0eacd7162fef6a25fe97bf527a25b"))


class EnterpriseConfigTests(IsolatedRuntimeMixin, unittest.TestCase):
    def test_enterprise_mode_requires_access_password(self):
        os.environ["ENTERPRISE_MODE"] = "true"
        os.environ["REQUIRE_ACCESS_PASSWORD"] = "true"
        get_settings.cache_clear()

        self.assertIn(
            "ACCESS_PASSWORD is required when REQUIRE_ACCESS_PASSWORD is enabled.",
            enterprise_warnings(),
        )

    def test_enterprise_mode_warns_about_reference_backends(self):
        os.environ["ENTERPRISE_MODE"] = "true"
        os.environ["REQUIRE_ACCESS_PASSWORD"] = "false"
        get_settings.cache_clear()

        warnings = enterprise_warnings()

        self.assertTrue(any("DATABASE_BACKEND=sqlite" in item for item in warnings))
        self.assertTrue(any("VECTOR_BACKEND=chroma" in item for item in warnings))


class RagEvaluationTests(unittest.TestCase):
    def test_score_case_detects_pii_and_forbidden_terms(self):
        from scripts.evaluate_rag import score_case

        metrics = score_case(
            "员工请假信息 test@example.com",
            ["policy-page-1"],
            ["请假"],
            forbidden_terms=["test@example.com"],
        )

        self.assertFalse(metrics["passed"])
        self.assertTrue(metrics["pii_leakage"])
        self.assertEqual(metrics["forbidden_hits"], ["test@example.com"])


if __name__ == "__main__":
    unittest.main()
