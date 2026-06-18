from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
import re
import smtplib
from typing import Any, Dict, Optional
from uuid import uuid4
from zoneinfo import ZoneInfo

from .ats import LocalATSAdapter
from .audit import write_audit_event
from .config import get_settings
from .database import create_interview_action
from .security import EMAIL_RE, redact_pii, stable_hash


LOCAL_TZ = ZoneInfo("Asia/Shanghai")
CN_NUMBERS = {
    "零": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


@dataclass(frozen=True)
class ToolExecutionResult:
    tool_name: str
    status: str
    message: str
    metadata: Dict[str, Any]

    def to_markdown(self) -> str:
        details = "\n".join([f"- {key}: {value}" for key, value in self.metadata.items()])
        if details:
            details = f"\n\n{details}"
        return f"**[{self.status}] {self.tool_name}**\n\n{self.message}{details}"


def _safe_slug(value: str) -> str:
    return stable_hash(value or str(uuid4()))


def _extract_email(*values: str) -> Optional[str]:
    for value in values:
        match = EMAIL_RE.search(value or "")
        if match:
            return match.group(0)
    return None


def _cn_number_to_int(value: str) -> Optional[int]:
    if value.isdigit():
        return int(value)
    if value in CN_NUMBERS:
        return CN_NUMBERS[value]
    if value.startswith("十") and len(value) == 2:
        return 10 + CN_NUMBERS.get(value[1], 0)
    if value.endswith("十") and len(value) == 2:
        return CN_NUMBERS.get(value[0], 0) * 10
    if "十" in value and len(value) == 3:
        return CN_NUMBERS.get(value[0], 0) * 10 + CN_NUMBERS.get(value[2], 0)
    return None


def parse_interview_window(interview_time: str, *, now: Optional[datetime] = None) -> Optional[tuple[datetime, datetime]]:
    text = (interview_time or "").strip()
    if not text:
        return None

    current = now.astimezone(LOCAL_TZ) if now else datetime.now(LOCAL_TZ)
    date_value: Optional[datetime] = None

    iso_match = re.search(r"(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})", text)
    cn_date_match = re.search(r"(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]", text)
    if iso_match:
        year, month, day = map(int, iso_match.groups())
        date_value = datetime(year, month, day, tzinfo=LOCAL_TZ)
    elif cn_date_match:
        month, day = map(int, cn_date_match.groups())
        date_value = datetime(current.year, month, day, tzinfo=LOCAL_TZ)
    elif "后天" in text:
        date_value = current + timedelta(days=2)
    elif "明天" in text:
        date_value = current + timedelta(days=1)
    elif "今天" in text or "今日" in text:
        date_value = current

    time_match = re.search(r"(\d{1,2})\s*[:点时]\s*(\d{1,2})?", text)
    cn_time_match = re.search(r"([一二两三四五六七八九十]{1,3})\s*[点时]", text)
    hour: Optional[int] = None
    minute = 0
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2) or 0)
    elif cn_time_match:
        hour = _cn_number_to_int(cn_time_match.group(1))

    if hour is None or date_value is None:
        return None

    if any(flag in text for flag in ("下午", "晚上", "傍晚")) and hour < 12:
        hour += 12
    if "中午" in text and hour < 11:
        hour += 12

    start = date_value.replace(hour=hour, minute=minute, second=0, microsecond=0)
    end = start + timedelta(hours=1)
    return start, end


def _ics_datetime(value: datetime) -> str:
    return value.strftime("%Y%m%dT%H%M%S")


def _escape_ics(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _build_email_message(candidate_name: str, interview_time: str, candidate_email: Optional[str]) -> EmailMessage:
    settings = get_settings()
    message = EmailMessage()
    message["Subject"] = f"面试邀约 - {candidate_name}"
    message["From"] = settings.smtp_from
    message["To"] = candidate_email or "candidate@example.com"
    message.set_content(
        f"""您好，{candidate_name}：

感谢您关注我们的岗位。现邀请您参加面试，时间为：{interview_time}。

请提前准备个人项目、AI Agent/RAG 相关经历，并回复确认是否方便。

PeopleOps Agent Platform
"""
    )
    return message


def _write_email_draft(candidate_name: str, interview_time: str, candidate_email: Optional[str]) -> Path:
    settings = get_settings()
    settings.email_draft_dir.mkdir(parents=True, exist_ok=True)
    draft_path = settings.email_draft_dir / f"interview_{_safe_slug(candidate_name + interview_time)}.eml"

    message = _build_email_message(candidate_name, interview_time, candidate_email)
    draft_path.write_text(message.as_string(), encoding="utf-8")
    return draft_path


def _send_email(candidate_name: str, interview_time: str, candidate_email: Optional[str]) -> str:
    settings = get_settings()
    if not settings.smtp_host:
        return "not_configured"
    if not candidate_email:
        return "missing_recipient"

    message = _build_email_message(candidate_name, interview_time, candidate_email)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username and settings.smtp_password:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)
    return "sent"


def _write_calendar_event(candidate_name: str, interview_time: str) -> Path:
    settings = get_settings()
    settings.calendar_dir.mkdir(parents=True, exist_ok=True)
    event_id = _safe_slug(candidate_name + interview_time)
    event_path = settings.calendar_dir / f"interview_{event_id}.ics"
    window = parse_interview_window(interview_time)
    dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if window:
        start, end = window
        schedule_lines = (
            f"DTSTART;TZID=Asia/Shanghai:{_ics_datetime(start)}\n"
            f"DTEND;TZID=Asia/Shanghai:{_ics_datetime(end)}\n"
        )
    else:
        schedule_lines = "X-REQUESTED-TIME:" + _escape_ics(interview_time) + "\n"

    event_path.write_text(
        f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//PeopleOps Agent Platform//Interview Scheduler//CN
CALSCALE:GREGORIAN
BEGIN:VEVENT
UID:{event_id}@peopleops-agent.local
DTSTAMP:{dtstamp}
{schedule_lines}SUMMARY:{_escape_ics("Interview with " + candidate_name)}
DESCRIPTION:{_escape_ics("Interview arranged by PeopleOps Agent Platform. Requested time: " + interview_time)}
END:VEVENT
END:VCALENDAR
""",
        encoding="utf-8",
    )
    return event_path


def schedule_interview(
    candidate_name: str,
    interview_time: str,
    *,
    candidate_email: Optional[str] = None,
    created_by: str = "local-admin",
) -> ToolExecutionResult:
    settings = get_settings()
    mode = settings.tool_execution_mode.lower()
    safe_candidate_name = redact_pii(candidate_name)
    safe_interview_time = redact_pii(interview_time)
    candidate_email = candidate_email or _extract_email(candidate_name, interview_time)
    safe_candidate_email = redact_pii(candidate_email or "")

    email_draft_path: Optional[Path] = None
    calendar_event_path: Optional[Path] = None
    ats_export_path: Optional[Path] = None
    smtp_status = "not_attempted"
    status = "DRY_RUN"

    if mode in {"local", "live"}:
        email_draft_path = _write_email_draft(candidate_name, interview_time, candidate_email)
        calendar_event_path = _write_calendar_event(candidate_name, interview_time)
        status = "PERSISTED"
        if mode == "live":
            smtp_status = _send_email(candidate_name, interview_time, candidate_email)

    action_id = create_interview_action(
        candidate_name=safe_candidate_name,
        interview_time=safe_interview_time,
        status=status,
        email_draft_path=email_draft_path,
        calendar_event_path=calendar_event_path,
        created_by=created_by,
    )
    if mode in {"local", "live"}:
        ats_export_path = LocalATSAdapter().sync_interview_action(
            {
                "action_id": action_id,
                "candidate_name": safe_candidate_name,
                "candidate_email": safe_candidate_email,
                "interview_time": safe_interview_time,
                "status": status,
                "email_draft_path": str(email_draft_path) if email_draft_path else None,
                "calendar_event_path": str(calendar_event_path) if calendar_event_path else None,
                "created_by": created_by,
            }
        )

    result = ToolExecutionResult(
        tool_name="schedule_interview",
        status=status,
        message=f"已为候选人【{safe_candidate_name}】生成面试邀约动作，并写入本地 ATS 数据库。",
        metadata={
            "action_id": action_id,
            "interview_time": safe_interview_time,
            "candidate_email": safe_candidate_email or "not_provided",
            "execution_mode": mode,
            "email_draft_path": str(email_draft_path) if email_draft_path else "dry_run",
            "calendar_event_path": str(calendar_event_path) if calendar_event_path else "dry_run",
            "ats_export_path": str(ats_export_path) if ats_export_path else "dry_run",
            "smtp_status": smtp_status,
            "ats_record": "interview_actions",
        },
    )

    write_audit_event(
        "tool.schedule_interview",
        {
            "candidate_ref": stable_hash(candidate_name),
            "interview_time": safe_interview_time,
            "candidate_email": safe_candidate_email,
            "execution_mode": mode,
            "smtp_status": smtp_status,
            "result": asdict(result),
        },
    )
    return result
