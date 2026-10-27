# Monynha Odoo MCP — Coolify (single-operator OAuth)

This deploys **one private operator's** existing Odoo connections, exposed as
an authenticated Streamable HTTP MCP resource server. This is **not** a
multi-tenant SaaS: every OAuth subject on the allowlist can access every Odoo
connection configured in this process, within its write policy. Use separate
deployments, keys and policies for separate customers or trust boundaries.

## Before deploying

1. Own an HTTPS hostname, e.g. `mcp.example.org`, pointed at Coolify.
2. Configure an **external OAuth 2.1 authorization server** (e.g. a suitably
   configured Keycloak realm). The MCP server **does not** provide an identity
   provider or issue access tokens.
3. Configure your authorization server for ChatGPT's authorization-code +
   PKCE S256 flow. It must publish OAuth authorization-server discovery,
   support **CIMD**, **DCR**, or a pre-registered ChatGPT client, pass the
   `resource=https://mcp.example.org/mcp` value through to the access token's
   audience, and provide the authorization-response `iss` parameter (RFC 9207)
   with matching discovery metadata.
4. Give the MCP resource server a confidential OAuth introspection client:
   HTTP Basic client credentials for its RFC 7662 `introspection_endpoint`.
   Introspection MUST return `active`, `iss`, `aud`, `sub`, `client_id`, `scope`,
   and `exp` for issued access tokens. Not all identity providers return all
   these claims by default; configure claim mappers or choose a compatible IdP.
   Tokens are rejected when even one check fails. Never use an IdP's **ID token**
   as a resource access token.
5. Restrict the OAuth subject allowlist to your own stable IdP `sub` value.
   A token for another account in the same realm is deliberately rejected.

**ChatGPT compatibility depends on this external IdP configuration.** A
working container and OAuth metadata alone are not proof of an end-to-end
ChatGPT login. Follow the [OpenAI OAuth guidance](https://developers.openai.com/plugins/build/auth)
for current callback/client-registration details.

## Recommended Coolify deployment (Dockerfile)

1. **New Resource → Application → Git Repository:**
   `marcelo-m7/odoo-mcp`, branch `feat/monynha-erp-mcp` for review; only use
   your approved stable branch for production.
2. Build Pack: **Dockerfile**, base directory `/`, Dockerfile `Dockerfile`.
   No custom start command: the image runs `uvicorn --factory` on `0.0.0.0:8000`.
3. **Ports Exposes:** `8000`. No direct host port mapping. Under **Domains**,
   attach `https://mcp.example.org`, internal service port `8000`.
4. Enable HTTPS/TLS and HTTP→HTTPS redirect in Coolify's proxy.
5. Set runtime variables/secrets, following
   [`examples/coolify.env.example`](../../examples/coolify.env.example).
   Mark credentials as secrets and do **not** make them build variables.
   If pasting JSON through Developer View, ensure values remain literal.
6. Use a **single instance / single worker**. This build uses one Uvicorn
   process and an in-memory MCP state; avoid horizontal scaling without a
   separate state/isolation design. Restrict deployment console access.
7. **Deploy**. The Dockerfile's health check requests `GET /health` using
   Python's stdlib; Coolify can consume this without `curl`/`wget`.

An optional `compose.coolify.yml` is included for Coolify's Docker Compose
source. Set its exposed service `mcp` to internal port `8000`, inject the same
secrets, and leave the host port unpublished. Compose also sets read-only
filesystem, no-new-privileges, dropped Linux capabilities and `/tmp` tmpfs.
Its optional Odoo API secret mapping is named `ODOO_FACODI_API_KEY` as an
example; extend the service `environment:` mapping if your connection profile
uses other `secret_env` names.

## Required configuration

| Variable | Purpose |
| --- | --- |
| `ODOO_MCP_TRANSPORT` | `streamable-http` (set by Docker image) |
| `MCP_PUBLIC_URL` | Exact externally visible resource URL, e.g. `https://mcp.example.org/mcp` |
| `MCP_OAUTH_ISSUER` | Exact issuer in the IdP's discovery metadata |
| `MCP_OAUTH_INTROSPECTION_URL` | HTTPS RFC 7662 endpoint |
| `MCP_OAUTH_CLIENT_ID` / `MCP_OAUTH_CLIENT_SECRET` | Secret for the IdP's **introspection client** (not the ChatGPT client) |
| `MCP_OAUTH_ALLOWED_SUBJECTS` | Comma-separated IdP subject IDs permitted to operate these Odoo connections |
| `MCP_OAUTH_REQUIRED_SCOPE` | One scope, recommended `odoo:mcp` |
| `ODOO_MCP_OPERATIONS_ENABLED` | `1` to register live Odoo tools; omit for documentation-only MCP |
| `ODOO_MCP_CONNECTIONS_JSON` | Startup profiles with `secret_env` **variable names** only |
| `ODOO_FACODI_API_KEY` | Example actual secret, injected as a Coolify runtime secret |
| `ODOO_MCP_WRITE_POLICY_JSON` | Omit for deny-by-default writes; grant only after explicit review |

Separate the Odoo API key from OAuth tokens. OAuth authorizes the MCP caller;
Odoo still enforces the permissions of the Odoo integration user. Use a
dedicated low-privilege Odoo account. **Do not paste an Odoo key into the
connections JSON, command-line arguments, image, or Git.**

No OAuth variables are optional in HTTP mode. A missing or invalid value makes
the process fail at startup rather than accidentally publish anonymous tools.

## Verification checklist

1. `https://mcp.example.org/health` → HTTP 200, `{"status":"ok"}`.
2. `https://mcp.example.org/.well-known/oauth-protected-resource/mcp` → HTTP
   200, exact `resource` and `authorization_servers` fields.
3. Anonymous `POST https://mcp.example.org/mcp` → HTTP **401**, with a
   `WWW-Authenticate` header pointing to protected-resource metadata.
4. Wrong/expired/revoked token, wrong issuer, audience, scope or `sub` → 401.
5. Valid OAuth access token for the allowed subject and resource → MCP
   `initialize`, `tools/list`, harmless `odoo_list_connections` and bounded
   read-only calls succeed. The IdP must allow the ChatGPT client flow.
6. Confirm writes denied unless explicitly allowed by the Odoo MCP policy.
   Run write-flow tests **only in a dedicated staging database**.
7. Check Coolify secrets are masked, logs have no tokens, and there are no
   unprotected host ports. Confirm egress firewall permits only required Odoo
   and IdP hosts; outbound DNS TOCTOU risk remains for Odoo connections.

Quick anonymous checks (safe):

```bash
curl -i https://mcp.example.org/health
curl -i https://mcp.example.org/.well-known/oauth-protected-resource/mcp
curl -i -X POST https://mcp.example.org/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
```

The last request **must not** reach an MCP operation without OAuth.

## Limits / go-live gates

- **Production readiness requires a separately configured and tested IdP.**
  This repository cannot provision or prove the OAuth authorization-code flow
  from an arbitrary customer's identity provider.
- Introspection is performed on every request (no positive caching). If the
  IdP is unavailable, access fails closed. Monitor latency and availability.
- This is a **single-owner** deployment, not per-user Odoo key isolation.
- Outbound Odoo hostname preflight does not pin resolved IPs. Until outbound
  DNS pinning or enforced network egress policy exists, do **not** treat the
  HTTP endpoint as a generic multi-tenant gateway or accept untrusted URLs.
- `GET /health` indicates process liveness, not IdP/Odoo operational health;
  use separate privileged monitoring for live connectivity.
- Docker build verification requires a Docker runtime. Never call this build
  production-validated without a real image build and authenticated E2E test.
