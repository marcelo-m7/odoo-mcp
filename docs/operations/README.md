# Remote Odoo Operations (optional MVP)

The development MCP remains the default. Remote ERP tools are **disabled** until
explicitly enabled for a trusted local MCP client. This is not yet an
authenticated multi-tenant hosted service.

## Configuration

Create a private environment variable containing the Odoo API key. Never place
its value in version control, MCP prompts, arguments or
`ODOO_MCP_CONNECTIONS_JSON`. The JSON below is a **profile definition**; the
`secret_env` value is the *name* of an environment variable, not the key.

```json
[
  {
    "id": "sample",
    "base_url": "https://odoo.example.com",
    "database": null,
    "protocol": "json2",
    "secret_env": "ODOO_SAMPLE_API_KEY"
  }
]
```

For local stdio clients, configure environment variables through the MCP
client's secret/environment settings:

- `ODOO_MCP_OPERATIONS_ENABLED=1` — register remote operations tools.
- `ODOO_MCP_CONNECTIONS_JSON` — JSON array like the example above.
- `ODOO_SAMPLE_API_KEY` — the actual API key stored in a private environment or
  secret manager. Never check it in.
- `ODOO_MCP_WRITE_POLICY_JSON` — optional JSON permissions; omitted means
  read-only operation.
- `ODOO_MCP_ALLOW_LOCAL=1` — **local development only**, permits HTTP loopback
  endpoints such as `http://127.0.0.1:8069`. Never enable on a hosted service.

### Policies

By default, creating, updating and deleting records are denied even if Odoo
would allow them. System models are denied except read-only model metadata.
For a single configured connection, a local policy can be:

```text
ODOO_MCP_WRITE_POLICY_JSON={"res.partner":["create","write"]}
```

With multiple connections, policies **must** explicitly name their target
connections; global grants are ignored:

```text
ODOO_MCP_WRITE_POLICY_JSON={"connections":{"staging":{"res.partner":["create","write","unlink"]}}}
```

Only `create`, `write` and `unlink` are valid write verbs. Odoo's own access
rights and record rules still apply. Do not grant dangerous operations in
production merely for testing; use a dedicated staging database.
The MVP deliberately accepts only scalar values for record creation/updates;
relational commands are rejected because they could create, modify or delete
records in other models without a separate policy decision.

### Legacy XML-RPC

For older Odoo versions, a profile can use `protocol: "xmlrpc"`, an explicit
`database`, `login_env` containing the environment-variable name for the Odoo
login, and `secret_env` containing the name for its API key. The protocol is
explicit, with no silent fallback from JSON-2 authorization errors. Prefer
JSON-2 on Odoo 19+, subject to the edition/subscription's external API access.

## Local usage and verification

After configuring the client environment, run the installed module as a stdio
server through the MCP client (e.g. command `uv`, arguments
`run`, `python`, `-m`, `odoo_mcp.server` from the repository directory).
The existing developer tools remain registered. Opt-in operations include
connection listing, model/field metadata, bounded search/get/aggregate and
single-record create/update/delete. With multiple profiles, pass `connection`
on every operation; otherwise the operation is rejected as ambiguous.

Offline verification:

```bash
uv sync
uv run pytest tests/operations -q
uv run python -m tests.test_server
uv run python test_imports.py
```

Use MCP Inspector against a test profile to confirm actual tool registration.
Any live integration test must use a dedicated test database. No production
connection is necessary for the offline suite.

## Operational limits and security notes

- JSON-2 calls use a Bearer API key and optionally `X-Odoo-Database`.
- Write operations are not automatically retried. Calls may trigger Odoo
  automations and cannot be universally simulated or rolled back.
- Each call is a separate Odoo transaction; a multi-step workflow is **not**
  atomic by default.
- There is no arbitrary model-method executor, payment posting, app installation,
  email sending, import/upsert or wizard completion in this MVP.
- The current stdio configuration trusts the local process owner. Do not expose
  Streamable HTTP to other users until authenticated gateway and tenant isolation
  controls are built and audited.
- Connections are configured once at startup. Changing a secret means updating
  the external secret and restarting the relevant MCP process; use dedicated
  API keys per integration and rotate/revoke them in Odoo.
- Production outbound calls preflight DNS answers and reject private destinations;
  DNS re-resolution between preflight and socket connection remains a limitation.
  Do not use this static local-trust configuration as an exposed multi-tenant
  gateway or accept connection URLs from untrusted callers. A hosted service
  needs address pinning and network egress controls as a separate security gate.
- Remote operations do not reuse the developer assistant's process-global
  `current_version`, so selecting documentation version cannot switch targets.

References: [Official Odoo 19 JSON-2 API](https://www.odoo.com/documentation/19.0/developer/reference/external_api.html),
[MCP tools specification](https://modelcontextprotocol.io/specification/2025-11-25/server/tools).
