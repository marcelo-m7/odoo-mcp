from __future__ import annotations

from html import escape
import json


def normalized_string_list(values: list[str] | None, fallback: list[str] | None = None) -> list[str]:
    if values is None:
        return list(fallback or [])
    cleaned: list[str] = []
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            cleaned.append(text)
    return cleaned


def js_string(value: str) -> str:
    return json.dumps(str(value))


def python_string(value: str) -> str:
    return repr(str(value))


def xml_text(value: str) -> str:
    return escape(str(value), quote=False)


def xml_attr(value: str) -> str:
    return escape(str(value), quote=True)
