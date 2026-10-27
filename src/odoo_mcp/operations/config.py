"""Static connection profiles and lazy environment credential lookup."""

from __future__ import annotations

import ipaddress
import json
import os
import re
import socket
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError


_ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")
_HOSTNAME = re.compile(r"^[a-z0-9-]+(?:\.[a-z0-9-]+)+$", re.I)
_NUMERIC_HOST_LABEL = re.compile(r"^(?:0x[0-9a-f]+|[0-9]+)$", re.I)


class ConnectionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    id: str
    base_url: str
    database: str | None = None
    protocol: Literal["json2", "xmlrpc"]
    secret_env: str = Field(repr=False)
    login_env: str | None = None


class EnvironmentCredentials:
    def get(self, env_name: str) -> str:
        if not _ENV_NAME.fullmatch(env_name):
            raise ValueError("Credential environment variable name is invalid")
        secret = os.environ.get(env_name)
        if not secret:
            raise ValueError("Credential environment variable is not configured")
        return secret


def _validate_url(url: str, allow_local: bool) -> str:
    value = urlsplit(url)
    if value.username or value.password or value.query or value.fragment or value.path not in ("", "/"):
        raise ValueError("Connection URL must be an origin without credentials, path or query")
    if value.scheme not in ("https", "http") or not value.hostname:
        raise ValueError("Connection URL must use HTTPS")
    host = value.hostname.lower().rstrip(".")
    loopback = host in ("localhost", "127.0.0.1", "::1")
    if value.scheme == "http" and not (allow_local and loopback):
        raise ValueError("HTTP is only allowed for loopback development")
    if loopback and not allow_local:
        raise ValueError("Local addresses are blocked")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and (not address.is_global) and not (allow_local and address.is_loopback):
        raise ValueError("Non-public IP addresses are blocked")
    if address is None and not loopback:
        if all(_NUMERIC_HOST_LABEL.fullmatch(label) for label in host.split(".")):
            raise ValueError("Ambiguous numeric IP host is blocked")
        if not _HOSTNAME.fullmatch(host) or host.endswith((".local", ".internal", ".localhost")):
            raise ValueError("A public DNS hostname is required")
    try:
        port = value.port
    except ValueError as exc:
        raise ValueError("Invalid connection port") from exc
    return f"{value.scheme}://{value.netloc.lower()}".rstrip("/")


def verify_public_destination(url: str, *, allow_local: bool = False) -> None:
    """Refuse connections when any currently resolved address is not public.

    This is a conservative preflight on a trusted static profile, not a
    substitute for socket-level DNS pinning in a future hosted service.
    """
    target = urlsplit(url)
    host = target.hostname
    if not host:
        raise ValueError("Invalid Odoo connection host")
    try:
        addresses = socket.getaddrinfo(host, target.port or (443 if target.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except (OSError, ValueError):
        raise ValueError("Unable to verify Odoo connection destination") from None
    if not addresses:
        raise ValueError("Unable to resolve Odoo connection destination")
    for entry in addresses:
        address = ipaddress.ip_address(entry[4][0])
        if not address.is_global and not (allow_local and address.is_loopback and target.scheme == "http"):
            raise ValueError("Connection resolves to a non-public address")


class ConnectionRegistry:
    def __init__(self, profiles: list[ConnectionConfig]) -> None:
        self._profiles = {profile.id: profile for profile in profiles}
        if len(self._profiles) != len(profiles):
            raise ValueError("duplicate connection id")

    @classmethod
    def from_json(cls, raw: str, *, allow_local: bool = False) -> "ConnectionRegistry":
        try:
            entries = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid connection configuration JSON") from exc
        if not isinstance(entries, list) or not entries:
            raise ValueError("At least one connection must be configured")
        profiles = []
        for item in entries:
            if not isinstance(item, dict):
                raise ValueError("Connections must be objects")
            if any(key in item for key in ("api_key", "password", "token", "secret")):
                raise ValueError("Inline credentials are forbidden")
            try:
                connection = ConnectionConfig.model_validate(item)
            except (ValidationError, ValueError):
                raise ValueError("Invalid connection profile") from None
            if not _ID.fullmatch(connection.id):
                raise ValueError("Invalid connection id")
            if not _ENV_NAME.fullmatch(connection.secret_env) or (
                connection.login_env and not _ENV_NAME.fullmatch(connection.login_env)
            ):
                raise ValueError("Invalid environment variable reference")
            connection = connection.model_copy(update={"base_url": _validate_url(connection.base_url, allow_local)})
            profiles.append(connection)
        return cls(profiles)

    def get(self, connection: str | None) -> ConnectionConfig:
        if connection is None:
            if len(self._profiles) != 1:
                raise ValueError("An explicit connection is required when multiple instances are configured")
            return next(iter(self._profiles.values()))
        if connection not in self._profiles:
            raise ValueError("Unknown Odoo connection")
        return self._profiles[connection]

    def list(self) -> list[dict[str, str | None]]:
        return [{"id": p.id, "base_url": p.base_url, "protocol": p.protocol, "database": p.database} for p in self._profiles.values()]

    def __len__(self) -> int:
        return len(self._profiles)
