import hashlib
import re
import secrets
from typing import Any, Dict, Iterable, List


PHONE_RE = re.compile(r"(?<!\d)(?:\+?86[-\s]?)?1[3-9]\d{9}(?!\d)")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
ID_CARD_RE = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")


def redact_pii(text: str) -> str:
    if not text:
        return ""

    redacted = PHONE_RE.sub("[手机号已脱敏]", text)
    redacted = EMAIL_RE.sub("[邮箱已脱敏]", redacted)
    redacted = ID_CARD_RE.sub("[身份证号已脱敏]", redacted)
    return redacted


def redact_messages(messages: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    return [
        {
            "role": message.get("role", ""),
            "content": redact_pii(str(message.get("content", ""))),
        }
        for message in messages
    ]


def redact_payload(value: Any) -> Any:
    if isinstance(value, str):
        return redact_pii(value)
    if isinstance(value, dict):
        return {key: redact_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_payload(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_payload(item) for item in value)
    return value


def hash_password(password: str) -> str:
    return "sha256:" + hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(input_password: str, expected_password: str | None) -> bool:
    if not expected_password:
        return True
    if expected_password.startswith("sha256:"):
        return secrets.compare_digest(hash_password(input_password), expected_password)
    return secrets.compare_digest(input_password, expected_password)


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
