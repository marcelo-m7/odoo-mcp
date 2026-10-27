import pytest

from odoo_mcp.operations.backends import make_backend
from odoo_mcp.operations.config import ConnectionConfig, EnvironmentCredentials
from odoo_mcp.operations.errors import OperationError
from odoo_mcp.operations.xmlrpc import XmlRpcBackend
from odoo_mcp.operations.xmlrpc import NoRetrySafeTransport
import http.client


class Common:
    calls = 0
    def authenticate(self, db, user, key, context):
        self.calls += 1
        assert (db, user, key) == ("demo", "mcp@example.com", "secret-test")
        return 7


class Objects:
    def __init__(self):
        self.calls = []

    def execute_kw(self, *args):
        self.calls.append(args)
        return [{"id": 1}]


def config(**values):
    return ConnectionConfig(id="legacy", base_url="https://example.com", database="demo", protocol="xmlrpc",
                            secret_env="ODOO_SECRET", login_env="ODOO_LOGIN").model_copy(update=values)


def test_xmlrpc_uses_execute_kw_and_authenticates_once(monkeypatch):
    monkeypatch.setenv("ODOO_SECRET", "secret-test")
    monkeypatch.setenv("ODOO_LOGIN", "mcp@example.com")
    common, objects = Common(), Objects()
    backend = XmlRpcBackend(config(), EnvironmentCredentials(), common=common, objects=objects)
    assert backend.call("res.partner", "read", ids=[1], kwargs={"fields": ["name"]}) == [{"id": 1}]
    assert backend.call("res.partner", "search_read", kwargs={"limit": 1}) == [{"id": 1}]
    assert common.calls == 1
    assert objects.calls[0] == ("demo", 7, "secret-test", "res.partner", "read", [[1]], {"fields": ["name"]})


@pytest.mark.parametrize("bad", [{"database": None}, {"login_env": None}])
def test_xmlrpc_needs_database_and_login(bad):
    with pytest.raises(OperationError):
        XmlRpcBackend(config(**bad), EnvironmentCredentials(), common=Common(), objects=Objects())


def test_xmlrpc_auth_failure_does_not_expose_key(monkeypatch):
    monkeypatch.setenv("ODOO_SECRET", "secret-test")
    monkeypatch.setenv("ODOO_LOGIN", "mcp@example.com")
    class BadCommon:
        def authenticate(self, *args): return False
    with pytest.raises(OperationError, match="authentication") as exc:
        XmlRpcBackend(config(), EnvironmentCredentials(), common=BadCommon(), objects=Objects()).call("res.partner", "read")
    assert "secret-test" not in str(exc.value)


def test_backend_factory_uses_explicit_protocol(monkeypatch):
    monkeypatch.setenv("ODOO_SECRET", "secret-test")
    monkeypatch.setenv("ODOO_LOGIN", "mcp@example.com")
    backend = make_backend(config(), EnvironmentCredentials(), common=Common(), objects=Objects())
    assert isinstance(backend, XmlRpcBackend)
    assert type(make_backend(config(protocol="json2"), EnvironmentCredentials())).__name__ == "Json2Backend"


def test_xmlrpc_create_uses_positional_values(monkeypatch):
    monkeypatch.setenv("ODOO_SECRET", "secret-test")
    monkeypatch.setenv("ODOO_LOGIN", "mcp@example.com")
    objects = Objects()
    backend = XmlRpcBackend(config(), EnvironmentCredentials(), common=Common(), objects=objects)
    backend.call("res.partner", "create", kwargs={"vals_list": [{"name": "A"}]})
    assert objects.calls[-1][5] == [[{"name": "A"}]]
    assert objects.calls[-1][6] == {}


def test_xmlrpc_transport_never_retries_a_disconnected_write(monkeypatch):
    transport = NoRetrySafeTransport(timeout=1.0)
    count = 0
    def interrupted(*args, **kwargs):
        nonlocal count
        count += 1
        raise http.client.RemoteDisconnected("no response")
    monkeypatch.setattr(transport, "single_request", interrupted)
    with pytest.raises(http.client.RemoteDisconnected):
        transport.request("odoo.example.com", "/xmlrpc/2/object", b"rpc")
    assert count == 1


def test_xmlrpc_transport_has_finite_timeout():
    transport = NoRetrySafeTransport(timeout=3.0)
    connection = transport.make_connection("odoo.example.com")
    assert connection.timeout == 3.0
