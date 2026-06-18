import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from core.auth import Principal, has_permission
from core.config import get_settings
from core.database import list_interview_actions
from core.matcher import normalize_analysis
from core.pdf_utils import extract_document_text
from core.security import redact_payload, redact_pii, verify_password
from core.tools import parse_interview_window, schedule_interview
from core.workflow import keyword_intent


class WorkflowIntentTests(unittest.TestCase):
    def test_keyword_intent_routes_action(self):
        self.assertEqual(keyword_intent("帮我给张三发送明天下午两点的面试邀约"), "action_tool")

    def test_keyword_intent_routes_resume(self):
        self.assertEqual(keyword_intent("评估一下这份简历和 JD 的匹配度"), "resume")

    def test_keyword_intent_routes_rag(self):
        self.assertEqual(keyword_intent("年假制度是什么？"), "rag")


class MatcherNormalizationTests(unittest.TestCase):
    def test_normalize_analysis_clamps_score_and_lists(self):
        result = normalize_analysis({"score": 120, "pros": "Python 经验", "cons": ["缺少管理经验"]})

        self.assertEqual(result["score"], 100)
        self.assertEqual(result["pros"], ["Python 经验"])
        self.assertEqual(result["cons"], ["缺少管理经验"])


class SecurityTests(unittest.TestCase):
    def test_redact_pii_masks_common_identifiers(self):
        text = "候选人电话 13812345678，邮箱 test@example.com，身份证 110101199003071234"

        redacted = redact_pii(text)

        self.assertNotIn("13812345678", redacted)
        self.assertNotIn("test@example.com", redacted)
        self.assertNotIn("110101199003071234", redacted)

    def test_verify_password_allows_empty_expected_password(self):
        self.assertTrue(verify_password("", None))
        self.assertTrue(verify_password("secret", "secret"))
        self.assertFalse(verify_password("wrong", "secret"))

    def test_redact_payload_masks_nested_values(self):
        payload = {"candidate": {"email": "test@example.com", "items": ["13812345678"]}}

        redacted = redact_payload(payload)

        self.assertEqual(redacted["candidate"]["email"], "[邮箱已脱敏]")
        self.assertEqual(redacted["candidate"]["items"][0], "[手机号已脱敏]")


class DocumentImportTests(unittest.TestCase):
    def test_extract_document_text_supports_plain_text(self):
        result = extract_document_text("候选人具备 Python 经验".encode("utf-8"), "resume.txt")

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
            )
        }
        root = Path(self._tmpdir.name)
        os.environ["APP_DB_PATH"] = str(root / "peopleops.sqlite3")
        os.environ["AUDIT_LOG_PATH"] = str(root / "audit" / "events.jsonl")
        os.environ["EMAIL_DRAFT_DIR"] = str(root / "email_drafts")
        os.environ["CALENDAR_DIR"] = str(root / "calendar")
        os.environ["ATS_EXPORT_DIR"] = str(root / "ats_exports")
        os.environ["TOOL_EXECUTION_MODE"] = "local"
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
    def test_parse_interview_window_handles_common_chinese_time(self):
        now = datetime(2026, 6, 18, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai"))

        window = parse_interview_window("明天下午两点", now=now)

        self.assertIsNotNone(window)
        self.assertEqual(window[0].strftime("%Y-%m-%d %H:%M"), "2026-06-19 14:00")
        self.assertEqual(window[1].strftime("%Y-%m-%d %H:%M"), "2026-06-19 15:00")

    def test_schedule_interview_returns_auditable_local_result(self):
        result = schedule_interview("张三", "2026-06-20 14:00", candidate_email="candidate@example.com")

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


class AuthorizationTests(unittest.TestCase):
    def test_role_permissions(self):
        self.assertTrue(has_permission(Principal("alice", "admin"), "users"))
        self.assertTrue(has_permission(Principal("bob", "hrbp"), "tool"))
        self.assertFalse(has_permission(Principal("viewer", "viewer"), "tool"))

    def test_api_permission_error_maps_to_403(self):
        from api import app, current_principal

        app.dependency_overrides[current_principal] = lambda: Principal("viewer", "viewer")
        try:
            response = TestClient(app).get("/interviews")
        finally:
            app.dependency_overrides.clear()

        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
