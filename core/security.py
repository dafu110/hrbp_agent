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

    redacted = PHONE_RE.sub("[PHONE_REDACTED]", text)
    redacted = EMAIL_RE.sub("[EMAIL_REDACTED]", redacted)
    redacted = ID_CARD_RE.sub("[ID_CARD_REDACTED]", redacted)
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


PBKDF2_ITERATIONS = 260_000


def hash_password(password: str, *, salt: str | None = None, iterations: int = PBKDF2_ITERATIONS) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def _verify_pbkdf2(input_password: str, expected_password: str) -> bool:
    try:
        _, iterations, salt, expected_digest = expected_password.split("$", 3)
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            input_password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations),
        ).hex()
    except (ValueError, TypeError):
        return False
    return secrets.compare_digest(actual, expected_digest)


def verify_password(input_password: str, expected_password: str | None) -> bool:
    if not expected_password:
        return True
    if expected_password.startswith("pbkdf2_sha256$"):
        return _verify_pbkdf2(input_password, expected_password)
    if expected_password.startswith("sha256:"):
        legacy = "sha256:" + hashlib.sha256(input_password.encode("utf-8")).hexdigest()
        return secrets.compare_digest(legacy, expected_password)
    return secrets.compare_digest(input_password, expected_password)


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
