import pytest

from odoo_mcp.operations.errors import OperationError
from odoo_mcp.operations.policy import Policy
from odoo_mcp.operations.service import OdooService

from .test_read_service import FakeBackend, make_service


def test_writes_are_denied_by_default_without_remote_calls():
    service, backends = make_service()
    with pytest.raises(OperationError):
        service.create("res.partner", {"name": "A"})
    with pytest.raises(OperationError):
        service.update("res.partner", 1, {"name": "B"})
    with pytest.raises(OperationError):
        service.delete("res.partner", 1)
    assert backends["a"].calls == []


def test_scoped_write_grant_executes_expected_orm_methods():
    service, backends = make_service()
    service.policy = Policy({"res.partner": frozenset({"create", "write", "unlink"})})
    backend = backends["a"]
    backend.call = lambda model, method, *, ids=None, kwargs=None: 3 if method == "create" else True
    assert service.create("res.partner", {"name": "A"}) == 3
    assert service.update("res.partner", 3, {"name": "B"}) is True
    assert service.delete("res.partner", 3) is True


def test_multi_connection_write_grant_is_instance_scoped():
    service, backends = make_service(two=True)
    service.policy = Policy.from_json('{"connections":{"a":{"res.partner":["write"]}}}')
    with pytest.raises(OperationError):
        service.update("res.partner", 1, {"name": "bad"}, connection="b")
    assert backends["b"].calls == []


def test_unscoped_legacy_write_policy_cannot_grant_multi_connection_access():
    service, backends = make_service(two=True)
    service.policy = Policy({"res.partner": frozenset({"write"})})
    with pytest.raises(OperationError):
        service.update("res.partner", 1, {"name": "bad"}, connection="a")
    assert not backends["a"].calls


def test_write_is_attempted_exactly_once_when_odoo_fails():
    service, backends = make_service()
    service.policy = Policy({"res.partner": frozenset({"create"})})
    calls = 0
    def fail(model, method, *, ids=None, kwargs=None):
        nonlocal calls
        calls += 1
        raise OperationError("odoo_unavailable", "Odoo request failed")
    backends["a"].call = fail
    with pytest.raises(OperationError):
        service.create("res.partner", {"name": "A"})
    assert calls == 1


@pytest.mark.parametrize("value", [{"bad;field": 1}, {}, {"name": object()}])
def test_invalid_write_payload_never_reaches_odoo(value):
    service, backends = make_service()
    service.policy = Policy({"res.partner": frozenset({"create"})})
    with pytest.raises(ValueError):
        service.create("res.partner", value)
    assert backends["a"].calls == []


@pytest.mark.parametrize("command", [[[2, 42, 0]], [[0, 0, {"name": "child"}]], [[1, 42, {"name": "edited"}]]])
def test_relational_commands_cannot_bypass_grants(command):
    service, backends = make_service()
    service.policy = Policy({"res.partner": frozenset({"write"})})
    with pytest.raises(ValueError, match="scalar"):
        service.update("res.partner", 1, {"child_ids": command})
    assert not backends["a"].calls


def test_invalid_created_record_id_is_rejected():
    service, backends = make_service()
    service.policy = Policy({"res.partner": frozenset({"create"})})
    backends["a"].call = lambda *args, **kwargs: [0]
    with pytest.raises(OperationError):
        service.create("res.partner", {"name": "A"})
