"""Security boundaries for the opt-in, single-operator remote MCP."""

import time

import httpx
import pytest

from odoo_mcp.hosted_auth import HostedConfig, IntrospectionTokenVerifier


VALID = {
    "MCP_PUBLIC_URL": "https://mcp.example.org/mcp",
    "MCP_OAUTH_ISSUER": "https://id.example.org/realms/monynha",
    "MCP_OAUTH_INTROSPECTION_URL": "https://id.example.org/realms/monynha/protocol/openid-connect/token/introspect",
    "MCP_OAUTH_CLIENT_ID": "mcp-resource",
    "MCP_OAUTH_CLIENT_SECRET": "private-secret",
    "MCP_OAUTH_ALLOWED_SUBJECTS": "operator-123",
    "MCP_OAUTH_REQUIRED_SCOPE": "odoo:mcp",
}


@pytest.mark.parametrize("missing", sorted(VALID))
def test_hosted_config_fails_closed_when_required_setting_missing(missing):
    with pytest.raises(ValueError):
        HostedConfig.from_env({key: val for key, val in VALID.items() if key != missing})


@pytest.mark.parametrize("key,bad", [
    ("MCP_PUBLIC_URL", "http://mcp.example.org/mcp"),
    ("MCP_PUBLIC_URL", "https://mcp.example.org/other"),
    ("MCP_PUBLIC_URL", "https://mcp.example.org/mcp?secret=x"),
    ("MCP_OAUTH_ISSUER", "http://id.example.org/realm"),
    ("MCP_OAUTH_INTROSPECTION_URL", "http://id.example.org/token"),
    ("MCP_OAUTH_INTROSPECTION_URL", "https://127.0.0.1/introspect"),
    ("MCP_OAUTH_INTROSPECTION_URL", "https://id.internal/introspect"),
    ("MCP_PUBLIC_URL", "https://127.1/mcp"),
    ("MCP_OAUTH_ALLOWED_SUBJECTS", "  ,  "),
    ("MCP_OAUTH_REQUIRED_SCOPE", " "),
])
def test_hosted_config_rejects_insecure_or_ambiguous_settings(key, bad):
    with pytest.raises(ValueError):
        HostedConfig.from_env({**VALID, key: bad})


def test_hosted_config_uses_full_mcp_resource_url_and_explicit_owner():
    config = HostedConfig.from_env(VALID)
    assert config.resource_url == "https://mcp.example.org/mcp"
    assert config.allowed_subjects == frozenset({"operator-123"})
    assert config.scope == "odoo:mcp"


def test_hosted_config_repr_does_not_disclose_introspection_secret():
    config = HostedConfig.from_env(VALID)
    assert "private-secret" not in repr(config)


def response_claims(**overrides):
    return {
        "active": True,
        "iss": VALID["MCP_OAUTH_ISSUER"],
        "aud": [VALID["MCP_PUBLIC_URL"]],
        "sub": "operator-123",
        "client_id": "chatgpt-client",
        "token_type": "Bearer",
        "scope": "openid odoo:mcp",
        "exp": int(time.time()) + 3600,
        **overrides,
    }


@pytest.mark.asyncio
async def test_introspection_accepts_only_active_correctly_scoped_token():
    async def handler(request: httpx.Request):
        assert request.method == "POST"
        assert request.url == VALID["MCP_OAUTH_INTROSPECTION_URL"]
        assert request.headers["authorization"].startswith("Basic ")
        assert request.content == b"token=operator-access-token"
        return httpx.Response(200, json=response_claims())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        token = await IntrospectionTokenVerifier(HostedConfig.from_env(VALID), client).verify_token("operator-access-token")
    assert token is not None
    assert token.client_id == "chatgpt-client"
    assert token.resource == VALID["MCP_PUBLIC_URL"]
    assert "odoo:mcp" in token.scopes


@pytest.mark.asyncio
@pytest.mark.parametrize("rejected", [
    {"active": False},
    {"iss": "https://attacker.example.org"},
    {"aud": "another-resource"},
    {"sub": "another-user"},
    {"scope": "openid profile"},
    {"exp": int(time.time()) - 120},
    {"exp": None},
    {"client_id": ""},
    {"sub": None},
    {"token_type": "Refresh"},
    {"token_type": "DPoP", "cnf": {"jkt": "sender-key-thumbprint"}},
    {"token_type": None},
    {"token_type": "Bearer", "cnf": {"x5t#S256": "client-certificate-thumbprint"}},
    {"token_use": "refresh"},
    {"nbf": int(time.time()) + 120},
    {"nbf": "tomorrow"},
])
async def test_introspection_denies_wrong_claims(rejected):
    async def handler(request):
        return httpx.Response(200, json=response_claims(**rejected))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert await IntrospectionTokenVerifier(HostedConfig.from_env(VALID), client).verify_token("other-token") is None


@pytest.mark.asyncio
@pytest.mark.parametrize("status,body", [(500, {}), (200, {"active": True}), (200, [1, 2]), (200, {"active": "true"})])
async def test_introspection_denies_broken_provider_responses(status, body):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(status, json=body))) as client:
        assert await IntrospectionTokenVerifier(HostedConfig.from_env(VALID), client).verify_token("x") is None


@pytest.mark.asyncio
async def test_introspection_fails_closed_on_network_timeout():
    def handler(request):
        raise httpx.ConnectTimeout("timed out")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert await IntrospectionTokenVerifier(HostedConfig.from_env(VALID), client).verify_token("x") is None
