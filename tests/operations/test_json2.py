import json

import httpx
import pytest

from odoo_mcp.operations.config import ConnectionConfig, EnvironmentCredentials
from odoo_mcp.operations.errors import OperationError, public_error
from odoo_mcp.operations.json2 import Json2Backend


def backend(monkeypatch, handler, database="demo"):
    monkeypatch.setenv("ODOO_TEST_SECRET", "sensitive-key-123")
    config = ConnectionConfig(
        id="demo", base_url="https://odoo.example.com", database=database,
        protocol="json2", secret_env="ODOO_TEST_SECRET",
    )
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return Json2Backend(config, EnvironmentCredentials(), client=client)


def test_json2_request_schema(monkeypatch):
    def respond(request):
        assert request.url.path == "/json/2/res.partner/search_read"
        assert request.headers["Authorization"] == "bearer sensitive-key-123"
        assert request.headers["X-Odoo-Database"] == "demo"
        assert json.loads(request.content) == {"domain": [["active", "=", True]], "limit": 2}
        return httpx.Response(200, json=[{"id": 17}])
    value = backend(monkeypatch, respond).call("res.partner", "search_read", kwargs={"domain": [["active", "=", True]], "limit": 2})
    assert value == [{"id": 17}]


def test_json2_recordset_ids(monkeypatch):
    def respond(request):
        assert json.loads(request.content) == {"ids": [10], "vals": {"name": "ok"}}
        return httpx.Response(200, json=True)
    assert backend(monkeypatch, respond, database=None).call("res.partner", "write", ids=[10], kwargs={"vals": {"name": "ok"}}) is True


@pytest.mark.parametrize("status,code", [(401, "odoo_auth"), (403, "odoo_access"), (404, "odoo_not_found"), (429, "odoo_rate_limit"), (500, "odoo_unavailable")])
def test_http_errors_are_sanitized(monkeypatch, status, code):
    def respond(request):
        return httpx.Response(status, json={"message": "sensitive-key-123 Traceback at /opt/odoo.py"})
    with pytest.raises(OperationError) as exc:
        backend(monkeypatch, respond).call("res.partner", "search_read")
    assert public_error(exc.value)["error"]["code"] == code
    assert "sensitive-key-123" not in str(exc.value)
    assert "Traceback" not in str(exc.value)


def test_redirect_is_refused_even_with_redirect_enabled_client(monkeypatch):
    def respond(request):
        return httpx.Response(302, headers={"location": "http://127.0.0.1/secret"})
    with pytest.raises(OperationError, match="redirect"):
        backend(monkeypatch, respond).call("res.partner", "search_read")


def test_malformed_success_response(monkeypatch):
    with pytest.raises(OperationError, match="invalid JSON"):
        backend(monkeypatch, lambda request: httpx.Response(200, text="not-json")).call("res.partner", "read")


def test_no_automatic_retry(monkeypatch):
    count = 0
    def respond(request):
        nonlocal count
        count += 1
        return httpx.Response(500, text="fail")
    with pytest.raises(OperationError):
        backend(monkeypatch, respond).call("res.partner", "write", ids=[2], kwargs={"vals": {}})
    assert count == 1


@pytest.mark.parametrize("status", [429, 502, 503, 504])
@pytest.mark.parametrize("method", ["create", "write", "unlink"])
def test_uncertain_mutation_http_error_must_not_recommend_retry(monkeypatch, status, method):
    """A proxy error may arrive after Odoo has already committed a mutation."""
    connection = backend(monkeypatch, lambda request: httpx.Response(status, text="upstream error"))
    with pytest.raises(OperationError) as caught:
        connection.call("res.partner", method, ids=[9] if method != "create" else None)
    assert caught.value.retryable is False


@pytest.mark.parametrize("status", [429, 502, 503, 504])
def test_transient_read_http_error_remains_retryable(monkeypatch, status):
    connection = backend(monkeypatch, lambda request: httpx.Response(status, text="upstream error"))
    with pytest.raises(OperationError) as caught:
        connection.call("res.partner", "search_read", kwargs={"domain": []})
    assert caught.value.retryable is True


@pytest.mark.parametrize("model,method", [("res.partner/../../attack", "read"), ("res.partner", "_sudo"), ("", "read")])
def test_invalid_method_path_is_rejected(monkeypatch, model, method):
    with pytest.raises(OperationError, match="Invalid"):
        backend(monkeypatch, lambda request: pytest.fail("must not contact server")).call(model, method)
