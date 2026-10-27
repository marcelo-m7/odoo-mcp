# Monynha Odoo MCP — Foundation MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add secure, optionally enabled multi-instance Odoo ORM operations to the existing development MCP without breaking its current tools.

**Architecture:** Preserve FastMCP `server.py` and existing domain facades. Add `operations/` with validated connection/secret resolution, policy, JSON-2 and XML-RPC backends, structured ORM services and opt-in tool registration. Keep all network calls behind mockable interfaces and keep the first release local/stdio-only for credentials; authenticated hosted transport is a separate plan.

**Tech Stack:** Python >=3.12, existing `mcp>=1.4.1`, Pydantic from MCP's dependency graph or declare directly, HTTPX for JSON-2, Python `xmlrpc.client` for legacy, pytest for new tests, uv/hatchling.

**Spec:** `docs/superpowers/specs/2026-10-27-monynha-odoo-mcp-design.md`

## Global Constraints

- Existing package `src/odoo_mcp`, current public tool names, resources, prompts, version behavior and MIT attribution remain intact.
- Operations are opt-in through `ODOO_MCP_OPERATIONS_ENABLED=1`; disabled by default.
- Configured connections use named environment-secret references, never inline API keys in JSON.
- More than one connection requires explicit `connection`; never mutate process-wide active connection.
- JSON-2 first on Odoo 19+, XML-RPC only for explicitly configured legacy compatibility; no silent fallback on denied auth.
- Read-only is the default policy; writes require model-and-verb grants; generic method execution is outside this MVP.
- No external writes or real Odoo tests against production databases.
- No hosted multi-user release before separate auth/tenant-isolation milestone.
- Tests must be deterministic/offline except an explicitly invoked staging smoke suite.

## File responsibility map

- `operations/config.py`: typed connection configuration, profile parsing, URL validation, environment credential resolver, registry selection.
- `operations/errors.py`: typed sanitized domain errors and public error formatter.
- `operations/policy.py`: deny-by-default authorization per model and action.
- `operations/backends.py`: `OdooBackend` protocol and backend factory.
- `operations/json2.py`: Odoo JSON-2 HTTP implementation.
- `operations/xmlrpc.py`: legacy XML-RPC implementation.
- `operations/service.py`: field/model discovery, bounded record queries and controlled writes.
- `operations/registration.py`: opt-in MCP tools and resource registration; no I/O when imported.
- `server.py`: minimal opt-in registration hook, preserving current entrypoint.
- `tests/operations/test_*.py`: isolated behavior/contract tests.
- `docs/operations/README.md`: installation, security and CLI examples.
- `pyproject.toml`, `uv.lock`: explicit HTTPX/Pydantic and test dependencies.

## Review Focus

1. **Two configured connections, no explicit target:** must fail with an ambiguity error, tested in Task 1.
2. **Malicious or local-network URLs in remote mode:** must reject credentials-in-URL, insecure schemes/private hosts, and redirect attempts, tested in Tasks 1 and 3.
3. **Secret/traceback in a 401/500 error:** must redact before MCP output and logs, tested in Tasks 2 and 3.
4. **Malformed search domain / excessive limit / negative offset:** must fail before an Odoo call, tested in Task 5.
5. **Partial or repeated side-effecting requests:** must accurately report failures and never retry writes automatically, tested in Task 6.

---

### Task 1: Connection profiles and credential boundary

**Files:**
- Create: `src/odoo_mcp/operations/__init__.py`
- Create: `src/odoo_mcp/operations/config.py`
- Test: `tests/operations/test_config.py`

**Interfaces:**
- `ConnectionConfig(id: str, base_url: str, database: str | None, protocol: Literal["json2", "xmlrpc"], secret_env: str, login_env: str | None = None)` (Pydantic model).
- `ConnectionRegistry.from_json(raw: str, *, allow_local: bool = False) -> ConnectionRegistry`.
- `ConnectionRegistry.get(connection: str | None) -> ConnectionConfig`.
- `EnvironmentCredentials.get(env_name: str) -> str` raises sanitized `ConfigurationError` if empty/unset.
- A single connection allows omitted target; two or more require a name. No global active-pointer setter.

- [ ] **Step 1: Write failing tests** `test_rejects_embedded_credentials`, `test_blocks_private_url_by_default`, `test_requires_explicit_target_for_two_profiles`, `test_secret_reference_only`, `test_accepts_one_https_profile`. Assert no network calls and no secret values appear in repr/errors.
- [ ] **Step 2: Run** `uv run pytest tests/operations/test_config.py -q`. Expected: FAIL (module absent).
- [ ] **Step 3: Implement** typed config and registry; require an environment-variable *name* for `secret_env`, reject JSON keys named `api_key`/`password`, normalize HTTPS origin without credentials/fragments/paths, resolve env values only when needed. `allow_local` may permit loopback-only HTTP, not arbitrary private addresses.
- [ ] **Step 4: Run** same tests; expected PASS.
- [ ] **Step 5: Commit** `git add src/odoo_mcp/operations tests/operations/test_config.py && git commit -m "feat: add isolated Odoo connection profiles"`.

### Task 2: Policy and sanitized errors

**Files:**
- Create: `src/odoo_mcp/operations/errors.py`
- Create: `src/odoo_mcp/operations/policy.py`
- Test: `tests/operations/test_policy.py`

**Interfaces:**
- `OperationError(code: str, message: str, *, retryable: bool = False)`.
- `public_error(exc: Exception) -> dict[str, object]` returns stable `{"success": false, "error": {"code": ..., "message": ..., "retryable": ...}}` without raw response bodies.
- `Policy(allowed_writes: Mapping[str, frozenset[str]] | None = None)`.
- `Policy.authorize(model: str, action: Literal["read", "create", "write", "unlink", "aggregate"]) -> None`; rejects `_*`/administrative models by default, reads on approved non-system models, writes only with grants.

- [ ] **Step 1: Write failing tests** for read access, denied writes, model-scoped grant, administrative model denial, 401 exception redaction and secrets in an Odoo traceback.
- [ ] **Step 2: Run** `uv run pytest tests/operations/test_policy.py -q`; expected FAIL.
- [ ] **Step 3: Implement** `OperationError`, safe error normalization, and policy; raw exceptions may be retained internally only with an explicit redacting logger.
- [ ] **Step 4: Run** same tests; expected PASS.
- [ ] **Step 5: Commit** `git add src/odoo_mcp/operations tests/operations/test_policy.py && git commit -m "feat: enforce Odoo operation policies"`.

### Task 3: JSON-2 adapter

**Files:**
- Create: `src/odoo_mcp/operations/backends.py`
- Create: `src/odoo_mcp/operations/json2.py`
- Modify: `pyproject.toml`, `uv.lock`
- Test: `tests/operations/test_json2.py`

**Interfaces:**
- `OdooBackend.call(model: str, method: str, *, ids: list[int] | None = None, kwargs: dict[str, object] | None = None) -> object` (Protocol).
- `Json2Backend(config: ConnectionConfig, credentials: EnvironmentCredentials, *, client: httpx.Client | None = None)` implements `OdooBackend`.
- Requests are `POST /json/2/<model>/<method>` with Bearer API key, `Content-Type: application/json`, optional database header, `ids` and keyword fields as JSON body. No redirects; finite timeout.

- [ ] **Step 1: Write failing tests** with `httpx.MockTransport`: header/body/path, 401/403, 429 and 5xx normalization, response content with secret/traceback, redirect refusal, malformed JSON and no automatic retry on POST.
- [ ] **Step 2: Run** `uv run pytest tests/operations/test_json2.py -q`; expected FAIL.
- [ ] **Step 3: Implement** strict model/method name validation and adapter. Declare `httpx`, `pydantic`, `pytest` explicitly in project/dev dependencies; regenerate `uv.lock` with uv. Mask all authentication material.
- [ ] **Step 4: Run** same tests; expected PASS.
- [ ] **Step 5: Commit** `git add src/odoo_mcp/operations tests/operations/test_json2.py pyproject.toml uv.lock && git commit -m "feat: support Odoo JSON-2 API"`.

### Task 4: Legacy XML-RPC adapter

**Files:**
- Create: `src/odoo_mcp/operations/xmlrpc.py`
- Modify: `src/odoo_mcp/operations/backends.py`
- Test: `tests/operations/test_xmlrpc.py`

**Interfaces:**
- `XmlRpcBackend(config: ConnectionConfig, credentials: EnvironmentCredentials, *, common: object | None = None, objects: object | None = None)` implements `OdooBackend`.
- Requires `database`, `login_env`, `secret_env`. Authenticates via `common.authenticate`, performs `objects.execute_kw`; mocks injectable. Transport is explicit, not a fallback triggered by a JSON-2 authorization error.
- `make_backend(config, credentials, **test_injections) -> OdooBackend` chooses by configured protocol.

- [ ] **Step 1: Write failing tests** for auth once per backend instance, ids/kwargs mapping, missing database/login, failed auth without credential leakage, no JSON-2 silent fallback.
- [ ] **Step 2: Run** `uv run pytest tests/operations/test_xmlrpc.py -q`; expected FAIL.
- [ ] **Step 3: Implement** XML-RPC `execute_kw` calls and factory. Keep backend instances per connection so auth is not shared across profiles.
- [ ] **Step 4: Run** same tests; expected PASS.
- [ ] **Step 5: Commit** `git add src/odoo_mcp/operations tests/operations/test_xmlrpc.py && git commit -m "feat: add explicit legacy Odoo adapter"`.

### Task 5: Metadata and bounded read service

**Files:**
- Create: `src/odoo_mcp/operations/service.py`
- Test: `tests/operations/test_read_service.py`

**Interfaces:**
- `OdooService(registry: ConnectionRegistry, backend_for: Callable[[ConnectionConfig], OdooBackend], policy: Policy)`.
- `OdooService.fields_get(model: str, *, connection: str | None = None) -> dict[str, object]`.
- `OdooService.model_list(*, connection: str | None = None, limit: int = 100) -> list[dict[str, object]]`.
- `OdooService.search(model: str, *, domain: list[object] | None = None, fields: list[str] | None = None, limit: int = 50, offset: int = 0, order: str = "", connection: str | None = None) -> dict[str, object]`.
- `OdooService.get(model: str, record_id: int, *, fields: list[str] | None = None, connection: str | None = None) -> dict[str, object]`.
- `OdooService.aggregate(model: str, *, domain: list[object] | None = None, groupby: list[str], aggregates: list[str], limit: int = 50, connection: str | None = None) -> list[dict[str, object]]`.
- Search limit 1..100, offset 0..10000, field selection <=50, bounded group-by and aggregate result size; reject malformed domain and unsafe order expressions locally.

- [ ] **Step 1: Write failing tests** for Odoo `fields_get`, `ir.model` listing, search domain/fields/limit/offset and count, no-results get, aggregate `read_group`, bad domain, limit >100, offset -1, unknown connection and cross-profile results.
- [ ] **Step 2: Run** `uv run pytest tests/operations/test_read_service.py -q`; expected FAIL.
- [ ] **Step 3: Implement** the service using only `OdooBackend.call`, `Policy.authorize` and `ConnectionRegistry.get`. Return safe metadata and page information; no raw RPC errors.
- [ ] **Step 4: Run** same tests; expected PASS.
- [ ] **Step 5: Commit** `git add src/odoo_mcp/operations/service.py tests/operations/test_read_service.py && git commit -m "feat: provide bounded Odoo model reads"`.

### Task 6: Controlled writes

**Files:**
- Modify: `src/odoo_mcp/operations/service.py`
- Test: `tests/operations/test_write_service.py`

**Interfaces:**
- `OdooService.create(model: str, values: dict[str, object], *, connection: str | None = None) -> int`.
- `OdooService.update(model: str, record_id: int, values: dict[str, object], *, connection: str | None = None) -> bool`.
- `OdooService.delete(model: str, record_id: int, *, connection: str | None = None) -> bool`.
- These methods call `Policy.authorize` before `create`, `write`, `unlink`; never retry automatically. Explicitly return a failure for the whole operation if Odoo raises; no false success/atomic-batch claims.

- [ ] **Step 1: Write failing tests** for denied-by-default create/write/delete; scoped write grant; write permissions not inherited across connections; one attempted RPC call on 500; external side effect/partial failure reported without retry.
- [ ] **Step 2: Run** `uv run pytest tests/operations/test_write_service.py -q`; expected FAIL.
- [ ] **Step 3: Implement** minimal single-record operations and normalized errors; bulk writes and import idempotency are a separate phase.
- [ ] **Step 4: Run** same tests; expected PASS.
- [ ] **Step 5: Commit** `git add src/odoo_mcp/operations/service.py tests/operations/test_write_service.py && git commit -m "feat: gate Odoo record writes by policy"`.

### Task 7: MCP opt-in registration and compatibility

**Files:**
- Create: `src/odoo_mcp/operations/registration.py`
- Modify: `src/odoo_mcp/server.py`
- Test: `tests/operations/test_registration.py`

**Interfaces:**
- `register_operations(mcp: FastMCP, service: OdooService, registry: ConnectionRegistry) -> None`.
- Tool names: `odoo_instance_list`, `odoo_server_info`, `odoo_model_list`, `odoo_fields_get`, `odoo_record_search`, `odoo_record_get`, `odoo_record_aggregate`, `odoo_record_create`, `odoo_record_update`, `odoo_record_delete`.
- Resource templates `odoo://{model}/record/{record_id}`, `odoo://{model}/fields`, `odoo://{model}/count` only if exactly one connection is available. In multi-connection mode rely on explicit tool arguments; no ambiguous resources.
- Server hook reads `ODOO_MCP_OPERATIONS_ENABLED=1`; when absent, no new tools or network calls.

- [ ] **Step 1: Write failing tests** checking existing FastMCP tool names and prompt/resource inventory unchanged when disabled, operations names when enabled, zero startup network calls, explicit connection routing and ambiguous resource omission.
- [ ] **Step 2: Run** `uv run pytest tests/operations/test_registration.py -q`; expected FAIL.
- [ ] **Step 3: Implement** registration wrappers. Keep functions small and delegate data behavior to `OdooService`; avoid introducing a global mutable connection/tenant pointer.
- [ ] **Step 4: Run** registration tests and `uv run python -m tests.test_server`; expected PASS both.
- [ ] **Step 5: Commit** `git add src/odoo_mcp/server.py src/odoo_mcp/operations/registration.py tests/operations/test_registration.py && git commit -m "feat: expose opt-in Odoo operations MCP tools"`.

### Task 8: Documentation and release gate

**Files:**
- Create: `docs/operations/README.md`
- Modify: `README.md`
- Test: `tests/operations/test_config.py` (documented config fixture)

**Interfaces:**
- Document `ODOO_MCP_OPERATIONS_ENABLED=1`, `ODOO_MCP_CONNECTIONS_JSON` (array of ConnectionConfig objects with `secret_env` references), `ODOO_MCP_WRITE_POLICY_JSON` (explicit model -> action grant mapping), and local dev-only loopback allowance.
- Provide minimal JSON-2/stdio example, Odoo version/plan caveats, warnings for production writes and secure secret rotation.

- [ ] **Step 1: Write failing test** loading a valid documented example config without contacting Odoo; check docs never contain a usable API key.
- [ ] **Step 2: Run** `uv run pytest tests/operations/test_config.py -q`; expected FAIL until example is wired.
- [ ] **Step 3: Add** `docs/operations/README.md`, update top-level README and examples with no credentials; describe opt-in behavior and security limits.
- [ ] **Step 4: Run** `uv run pytest tests/operations -q`, `uv run python -m tests.test_server`, `uv run python test_imports.py`; expected PASS. Run MCP Inspector and staging smoke only when test environment is supplied; mark these pending if unavailable.
- [ ] **Step 5: Commit** `git add README.md docs/operations tests/operations && git commit -m "docs: document Monynha operations MVP"`.

## Implementation self-review / sequencing

- Every requirement in the MVP is covered by Tasks 1–8; bulk import, wizards, payments, binary file transfer, hosted workspaces, auditing persistence and specialized skills are explicitly later milestones, **not** incomplete parts of this MVP.
- Review Focus cases map to Tasks 1, 2, 3, 5 and 6.
- Task 7 binds the interfaces from Tasks 1–6 without changing the existing developer-tool contracts.
- Do not merge merely because offline tests pass; collect MCP Inspector and staging evidence, a security review, and a manual verification of unchanged legacy operations.
- Commit each task independently and open a PR from `feat/monynha-erp-mcp` to `main`; no automatic merge without explicit request.
