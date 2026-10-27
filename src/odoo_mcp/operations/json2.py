"""JSON-2 backend: one HTTP call per Odoo ORM operation."""

from __future__ import annotations

import re
import os

import httpx

from .config import ConnectionConfig, EnvironmentCredentials, verify_public_destination
from .errors import OperationError


_MODEL_NAME = re.compile(r"^[a-z][a-z0-9_.]*$")
_METHOD_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_ERRORS = {
    400: ("odoo_bad_request", "Odoo rejected the request"),
    401: ("odoo_auth", "Odoo authentication failed"),
    403: ("odoo_access", "Odoo access was denied"),
    404: ("odoo_not_found", "Odoo model or method was not found"),
    429: ("odoo_rate_limit", "Odoo rate limit exceeded"),
}


class Json2Backend:
    def __init__(self, config: ConnectionConfig, credentials: EnvironmentCredentials,
                 *, client: httpx.Client | None = None):
        self.config = config
        self.credentials = credentials
        self._verify_destination = client is None
        self.client = client or httpx.Client(timeout=20.0, follow_redirects=False, trust_env=False)

    def call(self, model: str, method: str, *, ids: list[int] | None = None,
             kwargs: dict[str, object] | None = None) -> object:
        if not _MODEL_NAME.fullmatch(model) or not _METHOD_NAME.fullmatch(method) or method.startswith("_"):
            raise OperationError("invalid_method", "Invalid Odoo model or method")
        params: dict[str, object] = dict(kwargs or {})
        if "ids" in params:
            raise OperationError("invalid_arguments", "Record IDs must use the ids parameter")
        if ids is not None:
            params["ids"] = ids
        headers = {
            "Authorization": f"bearer {self.credentials.get(self.config.secret_env)}",
            "Content-Type": "application/json",
            "User-Agent": "monynha-odoo-mcp/2",
        }
        if self.config.database:
            headers["X-Odoo-Database"] = self.config.database
        try:
            if self._verify_destination:
                verify_public_destination(self.config.base_url, allow_local=os.environ.get("ODOO_MCP_ALLOW_LOCAL") == "1")
            response = self.client.post(
                f"{self.config.base_url}/json/2/{model}/{method}",
                headers=headers, json=params, timeout=20.0, follow_redirects=False,
            )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            retryable = method in ("read", "search_read", "search_count", "fields_get", "read_group")
            raise OperationError("odoo_unavailable", "Odoo is unavailable; the operation outcome may be unknown", retryable=retryable) from None
        except ValueError:
            raise OperationError("invalid_destination", "Odoo connection destination is unsafe or unavailable") from None
        if 300 <= response.status_code < 400:
            raise OperationError("odoo_redirect", "Odoo redirect was refused")
        if response.status_code >= 400:
            code, message = _ERRORS.get(response.status_code, ("odoo_unavailable", "Odoo request failed"))
            raise OperationError(code, message, retryable=response.status_code in (429, 502, 503, 504))
        try:
            return response.json()
        except ValueError:
            raise OperationError("invalid_response", "Odoo returned invalid JSON") from None
