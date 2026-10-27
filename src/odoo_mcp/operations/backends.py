"""Protocol boundary for official Odoo external APIs."""

from __future__ import annotations

from typing import Protocol


class OdooBackend(Protocol):
    def call(self, model: str, method: str, *, ids: list[int] | None = None,
             kwargs: dict[str, object] | None = None) -> object: ...


def make_backend(config, credentials, **test_injections) -> OdooBackend:
    if config.protocol == "json2":
        from .json2 import Json2Backend
        return Json2Backend(config, credentials, **{k: v for k, v in test_injections.items() if k == "client"})
    if config.protocol == "xmlrpc":
        from .xmlrpc import XmlRpcBackend
        return XmlRpcBackend(config, credentials, **{k: v for k, v in test_injections.items() if k in ("common", "objects")})
    raise ValueError("Unsupported Odoo API protocol")
