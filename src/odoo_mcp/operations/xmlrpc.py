"""Explicit legacy Odoo XML-RPC adapter for older installations."""

from __future__ import annotations

import re
import xmlrpc.client
import http.client
import threading
import os

from .config import ConnectionConfig, EnvironmentCredentials, verify_public_destination
from .errors import OperationError


_MODEL_NAME = re.compile(r"^[a-z][a-z0-9_.]*$")
_METHOD_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


class NoRetrySafeTransport(xmlrpc.client.SafeTransport):
    """HTTPS XML-RPC transport with bounded timeout and no automatic replay."""

    def __init__(self, timeout: float = 20.0):
        super().__init__()
        self.timeout = timeout

    def request(self, host, handler, request_body, verbose=False):
        return self.single_request(host, handler, request_body, verbose)

    def make_connection(self, host):
        if self._connection and host == self._connection[0]:
            return self._connection[1]
        chost, self._extra_headers, x509 = self.get_host_info(host)
        self._connection = host, http.client.HTTPSConnection(
            chost, context=self.context, timeout=self.timeout, **(x509 or {}),
        )
        return self._connection[1]


class NoRetryTransport(xmlrpc.client.Transport):
    """HTTP transport restricted to explicitly permitted local development."""

    def __init__(self, timeout: float = 20.0):
        super().__init__()
        self.timeout = timeout

    def request(self, host, handler, request_body, verbose=False):
        return self.single_request(host, handler, request_body, verbose)

    def make_connection(self, host):
        if self._connection and host == self._connection[0]:
            return self._connection[1]
        chost, self._extra_headers, _ = self.get_host_info(host)
        self._connection = host, http.client.HTTPConnection(chost, timeout=self.timeout)
        return self._connection[1]


class XmlRpcBackend:
    def __init__(self, config: ConnectionConfig, credentials: EnvironmentCredentials,
                 *, common: object | None = None, objects: object | None = None):
        if not config.database or not config.login_env:
            raise OperationError("odoo_config", "Legacy API requires a database and a login reference")
        self.config = config
        self.credentials = credentials
        self._verify_destination = common is None and objects is None
        transport_type = NoRetrySafeTransport if config.base_url.startswith("https://") else NoRetryTransport
        self.common = common if common is not None else xmlrpc.client.ServerProxy(
            f"{config.base_url}/xmlrpc/2/common", allow_none=True, transport=transport_type())
        self.objects = objects if objects is not None else xmlrpc.client.ServerProxy(
            f"{config.base_url}/xmlrpc/2/object", allow_none=True, transport=transport_type())
        self.uid: int | None = None
        self._lock = threading.Lock()

    def call(self, model: str, method: str, *, ids: list[int] | None = None,
             kwargs: dict[str, object] | None = None) -> object:
        if not _MODEL_NAME.fullmatch(model) or not _METHOD_NAME.fullmatch(method) or method.startswith("_"):
            raise OperationError("invalid_method", "Invalid Odoo model or method")
        assert self.config.login_env is not None and self.config.database is not None
        login = self.credentials.get(self.config.login_env)
        key = self.credentials.get(self.config.secret_env)
        if self._verify_destination:
            try:
                verify_public_destination(self.config.base_url, allow_local=os.environ.get("ODOO_MCP_ALLOW_LOCAL") == "1")
            except ValueError:
                raise OperationError("invalid_destination", "Odoo connection destination is unsafe or unavailable") from None
        with self._lock:
            return self._call_locked(model, method, ids=ids, kwargs=kwargs, login=login, key=key)

    def _call_locked(self, model, method, *, ids, kwargs, login, key):
        try:
            if self.uid is None:
                uid = self.common.authenticate(self.config.database, login, key, {})
                if not uid:
                    raise OperationError("odoo_auth", "Odoo authentication failed")
                self.uid = int(uid)
            positional = [ids] if ids is not None else []
            parameters = dict(kwargs or {})
            if method == "create" and "vals_list" in parameters:
                positional = [parameters.pop("vals_list")]
            return self.objects.execute_kw(
                self.config.database, self.uid, key, model, method, positional, parameters,
            )
        except OperationError:
            raise
        except (xmlrpc.client.Fault, xmlrpc.client.ProtocolError, OSError, ValueError) as exc:
            raise OperationError("odoo_legacy_error", "Legacy Odoo RPC operation failed") from None
