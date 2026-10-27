"""Second authorization boundary, stricter than Odoo's own permissions."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Literal

from .errors import OperationError


Action = Literal["read", "create", "write", "unlink", "aggregate"]
_MODEL = re.compile(r"^[a-z][a-z0-9_.]*$")
_WRITE_ACTIONS = frozenset({"create", "write", "unlink"})
_READABLE_METADATA = {"ir.model", "ir.model.fields"}
_SENSITIVE_MODELS = frozenset({
    "res.config.settings", "fetchmail.server", "payment.provider", "payment.token",
    "mail.mail", "mail.server", "iap.account", "oauth.provider", "auth.oauth.provider",
    "calendar.credentials", "google.drive", "microsoft.account", "ir.attachment",
})


class Policy:
    def __init__(self, allowed_writes: Mapping[str, frozenset[str]] | None = None,
                 per_connection_writes: Mapping[str, Mapping[str, frozenset[str]]] | None = None):
        self.allowed_writes = dict(allowed_writes or {})
        self.per_connection_writes = {key: dict(grants) for key, grants in (per_connection_writes or {}).items()}

    @classmethod
    def from_json(cls, raw: str | None) -> "Policy":
        if not raw:
            return cls()
        try:
            values = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid policy JSON") from exc
        if not isinstance(values, dict):
            raise ValueError("Invalid policy structure")
        if "connections" in values:
            if len(values) != 1 or not isinstance(values["connections"], dict):
                raise ValueError("Invalid policy connection structure")
            scoped = {}
            for connection, grants in values["connections"].items():
                if not isinstance(connection, str) or not connection or not isinstance(grants, dict):
                    raise ValueError("Invalid policy connection")
                scoped[connection] = cls._parse_grants(grants)
            return cls(per_connection_writes=scoped)
        return cls(cls._parse_grants(values))

    @staticmethod
    def _parse_grants(values: dict) -> dict[str, frozenset[str]]:
        grants: dict[str, frozenset[str]] = {}
        for model, verbs in values.items():
            if not isinstance(model, str) or not _MODEL.fullmatch(model):
                raise ValueError("Invalid policy model")
            if not isinstance(verbs, list) or any(verb not in _WRITE_ACTIONS for verb in verbs):
                raise ValueError("Invalid policy actions")
            grants[model] = frozenset(verbs)
        return grants

    def authorize(self, model: str, action: Action, *, connection: str | None = None,
                  allow_global: bool = True) -> None:
        if not _MODEL.fullmatch(model) or model.startswith("_"):
            raise OperationError("forbidden_model", "Model is not permitted")
        if model.startswith(("ir.", "base.", "res.users", "res.groups", "auth.", "oauth.")) or model in _SENSITIVE_MODELS:
            if model in _READABLE_METADATA and action == "read":
                return
            raise OperationError("forbidden_model", "System model is not permitted")
        if action in ("read", "aggregate"):
            return
        grants = self.per_connection_writes.get(connection or "", {}).get(model, frozenset())
        if allow_global:
            grants = grants | self.allowed_writes.get(model, frozenset())
        if action not in _WRITE_ACTIONS or action not in grants:
            raise OperationError("forbidden_action", "Operation is not permitted by the configured policy")
