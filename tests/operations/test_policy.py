import pytest

from odoo_mcp.operations.errors import OperationError, public_error
from odoo_mcp.operations.policy import Policy


def test_read_access_uses_read_only_default():
    policy = Policy()
    policy.authorize("res.partner", "read")
    policy.authorize("sale.order", "aggregate")
    with pytest.raises(OperationError, match="not permitted"):
        policy.authorize("res.partner", "create")


def test_scoped_write_grants_do_not_cover_other_models():
    policy = Policy({"res.partner": frozenset({"create", "write"})})
    policy.authorize("res.partner", "create")
    with pytest.raises(OperationError):
        policy.authorize("res.partner", "unlink")
    with pytest.raises(OperationError):
        policy.authorize("sale.order", "write")


def test_system_models_denied_except_read_only_schema():
    policy = Policy()
    policy.authorize("ir.model", "read")
    with pytest.raises(OperationError):
        policy.authorize("ir.config_parameter", "read")
    with pytest.raises(OperationError):
        policy.authorize("ir.model", "write")
    with pytest.raises(OperationError):
        policy.authorize("_private.model", "read")
    for model in ("res.config.settings", "fetchmail.server", "payment.provider"):
        with pytest.raises(OperationError):
            policy.authorize(model, "read")


def test_policy_json_rejects_invalid_verbs_and_defaults_to_readonly():
    Policy.from_json(None).authorize("res.partner", "read")
    with pytest.raises(OperationError):
        Policy.from_json(None).authorize("res.partner", "write")
    with pytest.raises(ValueError, match="Invalid policy"):
        Policy.from_json('{"res.partner":["admin"]}')
    with pytest.raises(ValueError):
        Policy.from_json("not json")
    Policy.from_json('{"res.partner":["create"]}').authorize("res.partner", "create")


def test_public_errors_do_not_echo_secret_or_traceback():
    error = OperationError("odoo_auth", "Authentication failed")
    assert public_error(error) == {"success": False, "error": {"code": "odoo_auth", "message": "Authentication failed", "retryable": False}}
    unknown = public_error(RuntimeError("api-key-123 Traceback at secret.py:4"))
    assert unknown["error"]["code"] == "internal_error"
    assert "api-key-123" not in str(unknown)
    assert "Traceback" not in str(unknown)
