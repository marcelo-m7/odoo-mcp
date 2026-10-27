"""Fail-closed OAuth resource-server configuration for single-owner hosting.

An independent OAuth 2.1 authorization server issues tokens. This MCP is
only a protected resource server; it does not issue credentials or authorize
new users. Tokens are checked remotely using RFC 7662 introspection.
"""

from __future__ import annotations

import ipaddress
import os
import re
import time
from dataclasses import dataclass, field
from typing import Mapping
from urllib.parse import urlsplit

import httpx
from mcp.server.auth.provider import AccessToken


def _https_url(value: str, name: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"{name} must be a public HTTPS URL without credentials, query or fragment")
    hostname = parsed.hostname
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        if hostname == "localhost" or hostname.endswith(".localhost"):
            raise ValueError(f"{name} cannot use localhost") from None
        if (
            not re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", hostname, re.IGNORECASE)
            or hostname.endswith((".local", ".internal"))
            or all(re.fullmatch(r"(?:0x[0-9a-f]+|[0-9]+)", label, re.IGNORECASE) for label in hostname.split("."))
        ):
            raise ValueError(f"{name} requires a public DNS-style hostname") from None
    else:
        raise ValueError(f"{name} must use a DNS hostname, not an IP literal")
    return value


@dataclass(frozen=True)
class HostedConfig:
    resource_url: str
    issuer_url: str
    introspection_url: str
    client_id: str
    client_secret: str = field(repr=False)
    allowed_subjects: frozenset[str]
    scope: str

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "HostedConfig":
        values = os.environ if env is None else env

        def required(name: str) -> str:
            value = values.get(name, "").strip()
            if not value:
                raise ValueError(f"Missing required hosted MCP setting: {name}")
            return value

        resource = _https_url(required("MCP_PUBLIC_URL"), "MCP_PUBLIC_URL")
        if urlsplit(resource).path != "/mcp":
            raise ValueError("MCP_PUBLIC_URL must end at the /mcp endpoint")
        issuer = _https_url(required("MCP_OAUTH_ISSUER"), "MCP_OAUTH_ISSUER")
        introspection = _https_url(required("MCP_OAUTH_INTROSPECTION_URL"), "MCP_OAUTH_INTROSPECTION_URL")
        subjects = frozenset(v.strip() for v in required("MCP_OAUTH_ALLOWED_SUBJECTS").split(",") if v.strip())
        if not subjects:
            raise ValueError("MCP_OAUTH_ALLOWED_SUBJECTS must list at least one subject identifier")
        scope = required("MCP_OAUTH_REQUIRED_SCOPE")
        if any(char.isspace() for char in scope):
            raise ValueError("MCP_OAUTH_REQUIRED_SCOPE must contain exactly one scope")
        return cls(
            resource_url=resource,
            issuer_url=issuer,
            introspection_url=introspection,
            client_id=required("MCP_OAUTH_CLIENT_ID"),
            client_secret=required("MCP_OAUTH_CLIENT_SECRET"),
            allowed_subjects=subjects,
            scope=scope,
        )


class IntrospectionTokenVerifier:
    """Verify bearer tokens with the trusted IdP on every request.

    Do not cache positive responses: revoked tokens must stop working as soon
    as the authorization server marks them inactive.
    """

    def __init__(self, config: HostedConfig, client: httpx.AsyncClient | None = None):
        self.config = config
        self._client = client

    async def verify_token(self, token: str) -> AccessToken | None:
        if not token:
            return None
        try:
            if self._client is None:
                async with httpx.AsyncClient(timeout=5.0, follow_redirects=False) as client:
                    response = await self._introspect(client, token)
            else:
                response = await self._introspect(self._client, token)
            if response.status_code != 200:
                return None
            claims = response.json()
            if not isinstance(claims, dict) or claims.get("active") is not True:
                return None
            # RFC 7662 can introspect refresh and sender-constrained tokens
            # as well as ordinary bearer access tokens. This resource server
            # has no proof-of-possession verification mechanism: fail closed.
            token_type = claims.get("token_type")
            if not isinstance(token_type, str) or token_type.casefold() != "bearer":
                return None
            if "cnf" in claims or ("token_use" in claims and claims["token_use"] != "access"):
                return None
            if claims.get("iss") != self.config.issuer_url:
                return None
            audience = claims.get("aud")
            if isinstance(audience, str):
                audience = [audience]
            if not isinstance(audience, list) or self.config.resource_url not in audience:
                return None
            if claims.get("sub") not in self.config.allowed_subjects:
                return None
            scopes_raw = claims.get("scope")
            if isinstance(scopes_raw, str):
                scopes = scopes_raw.split()
            elif isinstance(scopes_raw, list) and all(isinstance(x, str) for x in scopes_raw):
                scopes = scopes_raw
            else:
                return None
            if self.config.scope not in scopes:
                return None
            expiry = claims.get("exp")
            now = int(time.time())
            if type(expiry) is not int or expiry <= now:
                return None
            if "nbf" in claims and (type(claims["nbf"]) is not int or claims["nbf"] > now):
                return None
            client_id = claims.get("client_id")
            if not isinstance(client_id, str) or not client_id:
                return None
            return AccessToken(
                token=token,
                client_id=client_id,
                scopes=scopes,
                expires_at=expiry,
                resource=self.config.resource_url,
            )
        except (httpx.HTTPError, ValueError, TypeError):
            # Never include provider response bodies or credentials in logs.
            return None

    async def _introspect(self, client: httpx.AsyncClient, token: str) -> httpx.Response:
        return await client.post(
            self.config.introspection_url,
            data={"token": token},
            auth=(self.config.client_id, self.config.client_secret),
            headers={"Accept": "application/json"},
        )
