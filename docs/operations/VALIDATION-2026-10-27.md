# Monynha Odoo MCP — validation evidence (2026-10-27)

## Scope and environment

- Branch: `feat/monynha-erp-mcp` in `marcelo-m7/odoo-mcp`.
- A private, out-of-repository `mcp.env` supplied `ODOO_HOST`, `ODOO_USER`,
  and `ODOO_API_KEY`. The target resolved from that configuration was
  `https://facodi.com` (production). The key and user are **not** stored in
  this repository or copied to an MCP configuration file.
- Production validation is **read-only**. No write grants were configured and
  no create/update/delete request was sent to Odoo.

## Evidence gathered

| Check | Result | Details |
| --- | --- | --- |
| Full pytest suite | PASS | `91 passed in 0.72s` using `uv run pytest -q` outside sandbox thread restrictions |
| Original development MCP tests | PASS | `uv run python -m tests.test_server` |
| Import compatibility | PASS | `uv run python test_imports.py` |
| Real server tool registration | PASS | 34 tools, including the ten opt-in operations tools; original development tools still present |
| Runtime write policy | PASS | Attempt to call `odoo_record_create` was rejected with `forbidden_action` without reaching Odoo |
| System model boundary | PASS | Attempt to read `res.users` was rejected with `forbidden_model` without reaching Odoo |
| Credential boundary | PASS | Key not present in tool registration or denied operation output |
| Live JSON-2 authentication | **BLOCKED** | DNS resolution of `facodi.com` failed from the execution environment before any HTTP connection |
| Live model discovery, fields, search, get and aggregate | **BLOCKED** | Each attempted read failed with normalized `invalid_destination` due to the same DNS restriction |
| Live MCP Inspector against Odoo | **PENDING** | Requires an environment with outbound HTTPS/DNS access |
| Live staging write smoke | **PENDING** | Requires an isolated staging database and explicit write permissions; never run against FACODI production |

## Cause of integration blocker

`socket.getaddrinfo('facodi.com', 443)` consistently returned
`socket.gaierror: [Errno -3] Temporary failure in name resolution`, including
in the escalated executor. A direct `curl` also failed to reach the configured
HTTP proxy. The backend's DNS preflight blocked the request before sending an
Authorization header. **Do not disable destination verification to work around
this environment failure.** No conclusion about the validity of the API key or
Odoo endpoint can be made from these attempts.

## Reviewer release gates

1. Run the full offline suite and legacy regression checks again on the
   published feature branch.
2. From an environment with outbound HTTPS/DNS, use a dedicated, least-privilege
   Odoo API key to call `odoo_model_list`, `odoo_fields_get`,
   `odoo_record_search`, `odoo_record_get`, and `odoo_record_aggregate` against
   a dedicated staging database. Check actual payload schemas, ACLs and latency.
3. Validate connection-listing and policy denials through an MCP client or MCP
   Inspector, with operations enabled and disabled.
4. On isolated staging, separately authorize and test create/update/delete of
   disposable records, including Odoo automations and access-rule failures.
5. Review the DNS preflight/TOCTOU limitation and prohibit a public hosted
   deployment until authentication, tenant isolation, DNS pinning and egress
   policy are provided. This MVP is for locally trusted stdio clients only.
6. Keep the PR unmerged until these integration and security gates are signed
   off. No release-ready or production-write claim is supported yet.

The credential file must never be added to version control or attached to the
pull request.
