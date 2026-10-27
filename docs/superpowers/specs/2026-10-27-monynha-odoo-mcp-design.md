# Monynha Odoo MCP 2.0 — Design

**Date:** 2026-10-27  
**Repository:** `marcelo-m7/odoo-mcp`  
**Base:** `main`; feature branch `feat/monynha-erp-mcp`  
**Status:** Approved direction; design recorded for review before product-code implementation.

## Intent

Evolve the existing Odoo Development MCP into a modular, independently implemented, security-conscious Odoo development **and** operations MCP. The existing development tools remain available unchanged, while an optional ERP operations capability can connect to one or more Odoo instances through officially supported APIs. The primary use cases include FACODI, Boa Vista and other independent implementation clients, but the software must not contain client-specific logic or credentials.

This is behavioral compatibility work based on observable public tool contracts and Odoo APIs, **not** access to or copying of another vendor's private source.

## Current baseline and evidence

- The repository is an MIT-licensed fork/derivative with original attribution to Martin Egeskov; preserve original copyright and licence notices.
- `pyproject.toml`: Python >=3.12, `mcp>=1.4.1`, hatchling, `src/odoo_mcp`.
- `src/odoo_mcp/server.py`: FastMCP entry point; version-aware docs, scaffolding, source inspection, planning and diagnostic tools; resources and prompts.
- `src/odoo_mcp/domains/` already groups domain facades. Reuse this pattern.
- `src/odoo_mcp/runtime/state.py` contains process-global `current_version`; this is **not** a safe tenant/session boundary.
- `tests/test_server.py` provides a pre-existing test suite; maintain it during development.
- The observed comparison service exposes 35 tools, four Odoo resource templates and multi-instance routing. Tool description and metadata inspection is **not** proof that every operation works on each edition/version.

## Goals

1. Preserve existing MCP development-tool contracts, resources and prompts.
2. Provide optional Odoo remote operations using JSON-2 first on compatible Odoo versions and a clearly bounded legacy XML-RPC adapter.
3. Select an explicit connection per call, with a safe default only where a single connection is configured; no cross-client or cross-connection leakage.
4. Discover models and fields and safely search/read/create/update/delete records and aggregate data.
5. Honor the Odoo-side user's ACLs, record rules and field restrictions, plus stricter configurable MCP-side policy.
6. Emit structured results with meaningful errors, predictable pagination and sensitive-value redaction.
7. Support both `stdio` for local clients and Streamable HTTP for independently authenticated remote clients.
8. Progress toward workspaces, audited workflows and specialized Odoo skills through separate deliverables.

## Non-goals for the first deliverable

- Reproducing proprietary implementation details, licensing systems, branding or hosted workspace internals of the comparison service.
- Full SaaS user management, billing, payment registration, email sending, app installation or production migrations.
- Autonomous writes in production without deliberate configured policy and user/client approval.
- A promise of atomicity across independent Odoo API calls.
- Requiring a custom Odoo add-on, direct database access or privileged Odoo internal shell access.
- Removing or substantially rewriting the existing developer-assistant functionality.

## Architectural approaches considered

1. **Local-only MCP:** lowest operational complexity, but poor multi-client access.
2. **Hybrid modular gateway — selected:** preserve local FastMCP use, add independently configured operations, then authenticated hosted transport.
3. **Full SaaS from day one:** centralized management but premature complexity/security surface.

The hybrid approach fits the existing Python FastMCP project and allows staged delivery with independently testable capabilities.

## Architecture

```text
MCP clients (local stdio; later authenticated Streamable HTTP)
    |
FastMCP registration: development [existing] + operations [opt-in]
    |
domains/connections | domains/metadata | domains/records | domains/workflows (later)
    |
policy checks + connection registry + audit interface
    |
adapters/json2 | adapters/xmlrpc
    |
Odoo API key identities and their native record/access rules
```

Preserve `src/odoo_mcp/server.py` as the compatibility entrypoint; new modules register their tools without import-time network access. An operations-only entry point may be added, but existing local client configurations must still work.

### Connection and secret contract

A connection has `id`, `base_url`, optional `database`, `api_version` (`auto`, `json2`, `xmlrpc`) and a **secret reference**, never a credential value returned by a tool. Configured profiles for the first deliverable may come from environment/config references, validated at startup. In a multi-connection setup, tools require explicit `connection`; no mutable process-global active pointer.

Validation must prohibit non-HTTPS remote URLs except an explicit local-development mode, disallow embedded credentials and URL redirects to unapproved hosts, and avoid accidental SSRF through connection targets. API key material is excluded from logs, errors, MCP resources and tracing.

For a hosted deployment, tenant isolation and server-side authorization become mandatory; transport authentication must be implemented **before** hosting connections for separate customers.

### Backends and compatibility

- JSON-2: `POST /json/2/<model>/<method>`, Bearer API key, named JSON method parameters, optional `X-Odoo-Database`.
- XML-RPC: Odoo `/xmlrpc/2/common` and `/xmlrpc/2/object` compatibility adapter only where enabled, using `execute_kw`; never assume JSON-2 and XML-RPC method signatures are equivalent.
- `auto` probes supported capability using a non-mutating operation and selects a supported adapter; fail closed when neither works. No silent downgrade after authentication/policy failure.
- Standard model access and record-rule behavior remains defined by the Odoo user. Tool-side policy may further restrict operations.

The Odoo 19 docs describe JSON-2 and planned deprecation of legacy external RPC; the implementation must not hardcode calendar dates for server detection.

### Security policies

Policy evaluation precedes all remote operations. Default policy is read-only and deny-by-default for administrative/system models, method execution and write operations. An explicit scoped configuration grants create/update/delete on chosen models. Method execution has a separate allowlist, never arbitrary public-method execution solely on the basis of Odoo permissions. Destructive calls require a human approval boundary in the client workflow when applicable. No generic `dry_run` flag may claim safety for side-effecting server methods.

Multi-record modifications report partial failure accurately; external side effects are never automatically retried without idempotency. Secret redaction and correlation IDs cover success and error paths.

### Resources and tool contracts

Phase 1 provides `odoo_instance_list`, `odoo_server_info`, `odoo_model_list`, `odoo_fields_get`, `odoo_record_search`, `odoo_record_get`, `odoo_record_create`, `odoo_record_update`, `odoo_record_delete`, `odoo_record_aggregate`, and resource templates `odoo://{model}/record/{record_id}`, `odoo://{model}/fields`, `odoo://{model}/count`. Exact names may have an `erp_` prefix if existing names conflict, but should be consistently documented and fixed before implementation. Responses contain `connection`, `model`, `success` and either typed data or a typed error; never include secret or raw Odoo traceback by default.

`odoo_record_search` supports a validated domain, explicit field selection, pagination and sort. Aggregation accepts group-by fields only in allowed models and bounds the result size. For resources in multi-connection mode, no implicit tenant selection is permitted; if a URI cannot encode an authorized connection, the resource is unavailable rather than ambiguous.

### Capability phases

1. **Foundation MVP:** additive tool registration; config/secrets; JSON-2 and legacy adapter; metadata; read-only search/get/aggregate; writes behind explicit policy; unit/contract tests and basic integration smoke on an isolated Odoo instance.
2. **Workflow parity:** record import with external IDs, bulk operations, binary fields, chatter, method execution with wizard follow-up, payment flows and app listing/install safeguards. Each workflow's own design addresses side effects and supported editions.
3. **Hosted multi-tenant gateway:** authenticated Streamable HTTP, workspace roles and membership, secret storage/rotation, protected config changes, audit persistence, rate limits and quotas. Never expose this mode for customer secrets before isolation/security review.
4. **Intelligent specialization:** domain skills, dynamic model discovery, safe business workflows and curated optional add-on integrations.
5. **Compatibility/release:** cross-edition test matrix, structured behavioral parity reports, packaging, docs, deployment.

## Files and boundaries

Current `src/odoo_mcp/domains/*/facade.py` conventions remain. Expected new paths:

- `src/odoo_mcp/operations/registration.py`: registration of optional operations tools.
- `src/odoo_mcp/operations/connections.py`: validated connection registry and secret references.
- `src/odoo_mcp/operations/policy.py`: operation/method authorization.
- `src/odoo_mcp/operations/backends.py`: transport protocol and backend selection.
- `src/odoo_mcp/operations/json2.py`, `xmlrpc.py`: Odoo protocol implementations.
- `src/odoo_mcp/operations/metadata.py`, `records.py`: bounded read/write service functions.
- `src/odoo_mcp/operations/errors.py`: sanitized error categories.
- `tests/operations/`: isolated tests with HTTP/XML-RPC fakes and MCP registration checks.
- `docs/operations/`: connection setup, security and client use.

Do not move existing domain packages in the MVP. Larger reorganizations require their own proposal.

## First-deliverable acceptance

- Existing `python -m tests.test_server` completes successfully, with no tool-name regressions.
- All new tests pass on Python 3.12+, including denied writes by default, allowed writes on explicit model policy, multi-connection isolation, invalid URLs, 401/403/404/429/5xx handling, malformed domains, redaction and pagination bounds.
- A single process can address two fake instances without shared credentials/state.
- MCP Inspector shows existing developer tools and operations tools when opted in.
- Offline contract tests cover JSON-2 and XML-RPC; live smoke tests execute against a dedicated staging/test database only, never FACODI or Boa Vista production.
- At least one documented local `stdio` example; hosted mode remains disabled unless authentication and isolation have been implemented and verified.

## Risks and tradeoffs

- JSON-2 and legacy APIs differ, and Odoo Online external API access depends on subscription tier.
- Generic ORM operations can cause side effects through computed fields, constraints, automations and mail; tool classification by CRUD verb is insufficient.
- Some Odoo workflows require wizards or atomic server-side methods; deferred to phase 2.
- The existing global Odoo version setting is process-wide; new remote connection state must never reuse it for isolation.
- Existing tests are not proof of successful live remote integration; preserve an explicit evidence ledger.

## Approval / next step

This design codifies the approved hybrid approach in the existing repo. The corresponding **MVP implementation plan** is in `docs/superpowers/plans/2026-10-27-monynha-odoo-mcp-mvp.md`. Confirm the plan before any product-code implementation.
