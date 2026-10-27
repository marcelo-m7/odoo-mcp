import json

import pytest

from odoo_mcp.operations.config import ConnectionRegistry
from odoo_mcp.operations.errors import OperationError
from odoo_mcp.operations.policy import Policy
from odoo_mcp.operations.service import OdooService


class FakeBackend:
    def __init__(self, tag):
        self.tag = tag
        self.calls = []

    def call(self, model, method, *, ids=None, kwargs=None):
        self.calls.append((model, method, ids, kwargs))
        if method == "search_count": return 2
        if method == "fields_get": return {"name": {"type": "char"}}
        if method == "read_group": return [{"stage_id": [2, "Open"], "__count": 2}]
        if method == "read": return [{"id": ids[0], "name": self.tag}] if ids[0] != 404 else []
        return [{"id": 1, "name": self.tag}]


def make_service(two=False):
    config = [{"id": "a", "base_url": "https://a.example.com", "protocol": "json2", "secret_env": "KEY_A"}]
    if two:
        config.append({"id": "b", "base_url": "https://b.example.com", "protocol": "json2", "secret_env": "KEY_B"})
    registry = ConnectionRegistry.from_json(json.dumps(config))
    backends = {"a": FakeBackend("a"), "b": FakeBackend("b")}
    return OdooService(registry, lambda cfg: backends[cfg.id], Policy()), backends


def test_fields_and_models_discovery():
    service, backend = make_service()
    assert service.fields_get("res.partner") == {"name": {"type": "char"}}
    models = service.model_list(limit=10)
    assert models[0]["id"] == 1
    assert backend["a"].calls[-1][0:2] == ("ir.model", "search_read")


def test_search_includes_pagination_and_count():
    service, backend = make_service()
    result = service.search("res.partner", domain=[["active", "=", True]], fields=["name"], limit=7, offset=1, order="name asc")
    assert result == {"records": [{"id": 1, "name": "a"}], "total": 2, "limit": 7, "offset": 1}
    assert backend["a"].calls[0][3]["domain"] == [["active", "=", True]]
    assert backend["a"].calls[0][3]["fields"] == ["name"]


def test_get_one_and_missing():
    service, _ = make_service()
    assert service.get("res.partner", 8)["name"] == "a"
    with pytest.raises(OperationError, match="not found"):
        service.get("res.partner", 404)


def test_aggregate_calls_read_group():
    service, backend = make_service()
    result = service.aggregate("sale.order", groupby=["stage_id"], aggregates=["amount_total:sum"])
    assert result[0]["__count"] == 2
    assert backend["a"].calls[-1][1] == "read_group"


@pytest.mark.parametrize("inputs", [
    {"domain": "[]"},
    {"domain": [["x", "execute", "bad"]]},
    {"domain": [["x"]]},
    {"domain": [["__class__", "=", "x"]]},
    {"limit": 101},
    {"limit": 0},
    {"offset": -1},
    {"offset": 10001},
    {"fields": ["name"] * 51},
    {"order": "name; drop table ir_model"},
])
def test_bad_search_input_is_rejected_before_remote_call(inputs):
    service, backend = make_service()
    with pytest.raises((ValueError, OperationError)):
        service.search("res.partner", **inputs)
    assert backend["a"].calls == []


def test_connections_remain_isolated():
    service, backend = make_service(two=True)
    with pytest.raises(ValueError, match="explicit connection"):
        service.search("res.partner")
    assert service.search("res.partner", connection="b")["records"][0]["name"] == "b"
    assert not backend["a"].calls


def test_aggregate_denies_invalid_groupby():
    service, backend = make_service()
    with pytest.raises(ValueError):
        service.aggregate("sale.order", groupby=["foo;shutdown"], aggregates=["amount:sum"])
    assert not backend["a"].calls


def test_search_and_get_use_bounded_safe_default_fields():
    service, backend = make_service()
    service.search("res.partner")
    assert backend["a"].calls[0][3]["fields"] == ["id", "display_name"]
    service.get("res.partner", 1)
    assert backend["a"].calls[-1][3]["fields"] == ["id", "display_name"]
    with pytest.raises(ValueError):
        service.search("res.partner", fields=[])


@pytest.mark.parametrize("domain", [["|"], ["!"], ["&", ["name", "=", "x"]], [["name", [], "x"]]])
def test_incomplete_or_invalid_prefix_domain_is_rejected(domain):
    service, backend = make_service()
    with pytest.raises(ValueError):
        service.search("res.partner", domain=domain)
    assert not backend["a"].calls
