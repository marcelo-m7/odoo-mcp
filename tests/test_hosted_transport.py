"""ASGI deployment boundary: OAuth discovery and authenticated transport."""

import httpx
import pytest

from odoo_mcp.hosted_auth import HostedConfig, IntrospectionTokenVerifier
from odoo_mcp.server import build_mcp
from odoo_mcp.hosted import create_hosted_app


AUTH_ENV = {
    "MCP_PUBLIC_URL": "https://mcp.example.org/mcp",
    "MCP_OAUTH_ISSUER": "https://id.example.org/realms/monynha",
    "MCP_OAUTH_INTROSPECTION_URL": "https://id.example.org/realms/monynha/protocol/openid-connect/token/introspect",
    "MCP_OAUTH_CLIENT_ID": "mcp-resource",
    "MCP_OAUTH_CLIENT_SECRET": "secret",
    "MCP_OAUTH_ALLOWED_SUBJECTS": "operator-123",
    "MCP_OAUTH_REQUIRED_SCOPE": "odoo:mcp",
}


@pytest.mark.asyncio
async def test_oauth_resource_metadata_and_challenge(monkeypatch):
    for name, value in AUTH_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("ODOO_MCP_TRANSPORT", "streamable-http")
    app = build_mcp().streamable_http_app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://mcp.example.org") as client:
        metadata = await client.get("/.well-known/oauth-protected-resource/mcp")
        assert metadata.status_code == 200
        assert metadata.json()["resource"] == AUTH_ENV["MCP_PUBLIC_URL"]
        assert metadata.json()["authorization_servers"] == [AUTH_ENV["MCP_OAUTH_ISSUER"]]
        unauthorized = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
        assert unauthorized.status_code == 401
        assert "oauth-protected-resource/mcp" in unauthorized.headers["www-authenticate"]


@pytest.mark.asyncio
async def test_hosted_health_is_public_but_mcp_is_protected(monkeypatch):
    for name, value in AUTH_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("ODOO_MCP_TRANSPORT", "streamable-http")
    app = create_hosted_app(build_mcp())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8000") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        unauthorized = await client.get("/mcp")
        assert unauthorized.status_code == 401


def test_hosted_app_refuses_to_start_without_explicit_authenticated_transport(monkeypatch):
    monkeypatch.delenv("ODOO_MCP_TRANSPORT", raising=False)
    with pytest.raises(RuntimeError, match="streamable-http"):
        create_hosted_app(build_mcp())


def test_http_transport_requires_oauth_settings_even_with_operations_disabled(monkeypatch):
    monkeypatch.setenv("ODOO_MCP_TRANSPORT", "streamable-http")
    monkeypatch.delenv("MCP_PUBLIC_URL", raising=False)
    with pytest.raises(ValueError, match="MCP_PUBLIC_URL"):
        build_mcp()


@pytest.mark.asyncio
async def test_valid_oauth_token_can_initialize_mcp_but_unapproved_subject_cannot(monkeypatch):
    for name, value in AUTH_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("ODOO_MCP_TRANSPORT", "streamable-http")

    import time
    from urllib.parse import parse_qs

    async def introspect(request):
        assert request.method == "POST"
        supplied = parse_qs(request.content.decode())["token"][0]
        return httpx.Response(200, json={
            "active": True,
            "iss": AUTH_ENV["MCP_OAUTH_ISSUER"],
            "aud": AUTH_ENV["MCP_PUBLIC_URL"],
            "sub": "operator-123" if supplied in {"valid-token", "dpop-token"} else "untrusted",
            "client_id": "chatgpt",
            "token_type": "DPoP" if supplied == "dpop-token" else "Bearer",
            "scope": "odoo:mcp",
            "exp": int(time.time()) + 600,
        })

    server = build_mcp()
    async with httpx.AsyncClient(transport=httpx.MockTransport(introspect)) as idp_client:
        server._token_verifier = IntrospectionTokenVerifier(HostedConfig.from_env(AUTH_ENV), idp_client)
        app = create_hosted_app(server)
        payload = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "integration-test", "version": "1"},
        }}
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://mcp.example.org") as client:
                bad = await client.post("/mcp", json=payload, headers={
                    "Accept": "application/json, text/event-stream", "Authorization": "Bearer invalid-token",
                })
                assert bad.status_code == 401
                unproven = await client.post("/mcp", json=payload, headers={
                    "Accept": "application/json, text/event-stream", "Authorization": "Bearer dpop-token",
                })
                assert unproven.status_code == 401
                accepted = await client.post("/mcp", json=payload, headers={
                    "Accept": "application/json, text/event-stream", "Authorization": "Bearer valid-token",
                })
                assert accepted.status_code == 200
                assert accepted.json()["result"]["serverInfo"]["name"] == "Monynha Odoo MCP"
