"""Optional FastMCP endpoints backed by a policy-protected OdooService."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from anyio import to_thread
from mcp.server.fastmcp import FastMCP
from pydantic import StrictInt

from .config import ConnectionRegistry
from .errors import OperationError, public_error
from .service import OdooService


def register_operations(mcp: FastMCP, service: OdooService, registry: ConnectionRegistry) -> None:
    def execute(callback: Callable[[], Any], connection: str | None = None) -> dict[str, object]:
        try:
            profile = registry.get(connection)
            return {"success": True, "connection": profile.id, "data": callback()}
        except ValueError:
            return public_error(OperationError("invalid_connection", "Invalid or ambiguous Odoo connection or parameters"))
        except Exception as exc:
            return public_error(exc)

    async def execute_async(callback: Callable[[], Any], connection: str | None = None) -> dict[str, object]:
        return await to_thread.run_sync(lambda: execute(callback, connection))

    @mcp.tool()
    def odoo_instance_list() -> dict[str, object]:
        """List configured Odoo connections without revealing secrets."""
        return {"success": True, "data": registry.list()}

    @mcp.tool()
    def odoo_server_info(connection: str | None = None) -> dict[str, object]:
        """Show the configured Odoo endpoint and API transport."""
        return execute(lambda: registry.get(connection).model_dump(exclude={"secret_env", "login_env"}), connection)

    @mcp.tool()
    async def odoo_model_list(limit: StrictInt = 100, connection: str | None = None) -> dict[str, object]:
        """Discover Odoo models subject to the current API user's access."""
        return await execute_async(lambda: service.model_list(limit=limit, connection=connection), connection)

    @mcp.tool()
    async def odoo_fields_get(model: str, connection: str | None = None) -> dict[str, object]:
        """Discover field metadata for a permitted Odoo model."""
        return await execute_async(lambda: service.fields_get(model, connection=connection), connection)

    @mcp.tool()
    async def odoo_record_search(model: str, domain: list[Any] | None = None,
                           fields: list[str] | None = None, limit: StrictInt = 50,
                           offset: StrictInt = 0, order: str = "",
                           connection: str | None = None) -> dict[str, object]:
        """Search Odoo records with a bounded domain, field set and page."""
        return await execute_async(lambda: service.search(model, domain=domain, fields=fields, limit=limit,
                                              offset=offset, order=order, connection=connection), connection)

    @mcp.tool()
    async def odoo_record_get(model: str, record_id: StrictInt, fields: list[str] | None = None,
                        connection: str | None = None) -> dict[str, object]:
        """Read one Odoo record by ID."""
        return await execute_async(lambda: service.get(model, record_id, fields=fields, connection=connection), connection)

    @mcp.tool()
    async def odoo_record_aggregate(model: str, groupby: list[str], aggregates: list[str],
                              domain: list[Any] | None = None, limit: StrictInt = 50,
                              connection: str | None = None) -> dict[str, object]:
        """Aggregate records by permitted Odoo fields."""
        return await execute_async(lambda: service.aggregate(model, domain=domain, groupby=groupby,
                                                 aggregates=aggregates, limit=limit, connection=connection), connection)

    @mcp.tool()
    async def odoo_record_create(model: str, values: dict[str, Any],
                           connection: str | None = None) -> dict[str, object]:
        """Create an Odoo record only when a model-scoped write policy permits it."""
        return await execute_async(lambda: service.create(model, values, connection=connection), connection)

    @mcp.tool()
    async def odoo_record_update(model: str, record_id: StrictInt, values: dict[str, Any],
                           connection: str | None = None) -> dict[str, object]:
        """Update one Odoo record subject to explicit write authorization."""
        return await execute_async(lambda: service.update(model, record_id, values, connection=connection), connection)

    @mcp.tool()
    async def odoo_record_delete(model: str, record_id: StrictInt,
                           connection: str | None = None) -> dict[str, object]:
        """Delete one Odoo record subject to explicit delete authorization."""
        return await execute_async(lambda: service.delete(model, record_id, connection=connection), connection)

    if len(registry) == 1:
        @mcp.resource("odoo://{model}/record/{record_id}")
        async def odoo_record_resource(model: str, record_id: str) -> str:
            return json.dumps(await odoo_record_get(model, int(record_id)))

        @mcp.resource("odoo://{model}/fields")
        async def odoo_fields_resource(model: str) -> str:
            return json.dumps(await odoo_fields_get(model))

        @mcp.resource("odoo://{model}/count")
        async def odoo_count_resource(model: str) -> str:
            response = await odoo_record_search(model, limit=1, fields=["id"])
            if not response["success"]:
                return json.dumps(response)
            return json.dumps({"success": True, "total": response["data"]["total"]})
