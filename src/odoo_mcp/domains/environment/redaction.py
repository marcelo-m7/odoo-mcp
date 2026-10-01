from __future__ import annotations

import re

SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?i)\b([A-Z0-9_-]*(?:PASSWORD|PASSWD|PWD|SECRET|TOKEN|API[_-]?KEY|ACCESS[_-]?KEY)[A-Z0-9_-]*)(\s*[:=]\s*)([^\s`'\",]+)"
)
CLI_SECRET_VALUE_RE = re.compile(
    r"(?i)(--(?:db[-_]?password|password|token|secret|api[-_]?key)|-w)(\s+)([^\s`]+)"
)
CLI_SECRET_EQUALS_RE = re.compile(
    r"(?i)(--(?:db[-_]?password|password|token|secret|api[-_]?key)=)([^\s`]+)"
)
URL_CREDENTIALS_RE = re.compile(r"://([^:/\s]+):([^@\s]+)@")


def redact_sensitive_text(value: str) -> str:
    text = str(value)
    text = URL_CREDENTIALS_RE.sub(r"://\1:***@", text)
    text = CLI_SECRET_EQUALS_RE.sub(r"\1***", text)
    text = CLI_SECRET_VALUE_RE.sub(r"\1\2***", text)
    text = SENSITIVE_ASSIGNMENT_RE.sub(r"\1\2***", text)
    return text
