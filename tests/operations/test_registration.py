import json
import asyncio

import pytest
from mcp.server.fastmcp import FastMCP

from odoo_mcp.operations.config import ConnectionRegistry
from odoo_mcp.operations.policy import Policy
from odoo_mcp.operations.registration import register_operations
from odoo_mcp.operations.service import OdooService

from .test_read_service import FakeBackend


def setup_mcp(two=False):
    raw = [{"id": "a", "base_url": "https://a.example.com", "protocol": "json2", "secret_env": "KEY_A"}]
    if two:
        raw.append({"id": "b", "base_url": "https://b.example.com", "protocol": "json2", "secret_env": "KEY_B"})
    registry = ConnectionRegistry.from_json(json.dumps(raw))
    backends = {"a": FakeBackend("a"), "b": FakeBackend("b")}
    mcp = FastMCP("operations-test")
    service = OdooService(registry, lambda cfg: backends[cfg.id], Policy())
    register_operations(mcp, service, registry)
    return mcp, service, backends


def test_registers_expected_operation_tools():
    mcp, _, _ = setup_mcp()
    tools = {tool.name for tool in mcp._tool_manager.list_tools()}
    assert tools == {
        "odoo_instance_list", "odoo_server_info", "odoo_model_list", "odoo_fields_get",
        "odoo_record_search", "odoo_record_get", "odoo_record_aggregate", "odoo_record_create",
        "odoo_record_update", "odoo_record_delete",
    }


def test_read_resources_registered_only_for_single_connection():
    one, _, _ = setup_mcp()
    two, _, _ = setup_mcp(two=True)
    assert len(one._resource_manager._templates) == 3
    assert len(two._resource_manager._templates) == 0


@pytest.mark.asyncio
async def test_count_resource_preserves_delegated_policy_error():
    mcp, _, _ = setup_mcp()
    contents = await mcp.read_resource("odoo://res.users/count")
    response = json.loads(contents[0].content)
    assert response["success"] is False
    assert response["error"]["code"] == "forbidden_model"
    assert response["error"]["retryable"] is False
    assert "total" not in response


@pytest.mark.asyncio
async def test_count_resource_returns_total_on_success():
    mcp, _, _ = setup_mcp()
    contents = await mcp.read_resource("odoo://res.partner/count")
    assert json.loads(contents[0].content) == {"success": True, "total": 2}


def test_tool_invocation_routes_to_explicit_connection():
    mcp, _, backends = setup_mcp(two=True)
    tool = mcp._tool_manager.get_tool("odoo_record_search")
    result = asyncio.run(tool.fn(model="res.partner", connection="b"))
    assert result["data"]["records"][0]["name"] == "b"
    assert backends["a"].calls == []


def test_errors_are_structured_and_redacted():
    mcp, _, _ = setup_mcp(two=True)
    result = asyncio.run(mcp._tool_manager.get_tool("odoo_record_search").fn(model="res.partner"))
    assert result["success"] is False
    assert result["error"]["code"] == "internal_error" or result["error"]["code"] == "invalid_connection"


def test_server_default_has_legacy_tools_and_no_operations(monkeypatch):
    monkeypatch.delenv("ODOO_MCP_OPERATIONS_ENABLED", raising=False)
    from odoo_mcp.server import mcp
    names = {tool.name for tool in mcp._tool_manager.list_tools()}
    assert "create_odoo_module" in names
    assert "search_documentation" in names
    assert "odoo_record_search" not in names


def test_actual_mcp_tool_rejects_boolean_record_id():
    mcp, _, backends = setup_mcp()
    tool = mcp._tool_manager.get_tool("odoo_record_delete")
    with pytest.raises(Exception):
        asyncio.run(tool.run({"model": "res.partner", "record_id": True}))
    assert not backends["a"].calls


def test_remote_mcp_wrappers_are_async():
    import inspect
    mcp, _, _ = setup_mcp()
    assert inspect.iscoroutinefunction(mcp._tool_manager.get_tool("odoo_record_search").fn)
