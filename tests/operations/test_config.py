import json
import re
from pathlib import Path

import pytest

from odoo_mcp.operations.config import (
    ConnectionRegistry,
    EnvironmentCredentials,
    verify_public_destination,
)


def profile(name="primary", url="https://example.odoo.com", **extra):
    return {
        "id": name,
        "base_url": url,
        "database": None,
        "protocol": "json2",
        "secret_env": "ODOO_KEY_PRIMARY",
        **extra,
    }


def test_accepts_one_https_profile():
    registry = ConnectionRegistry.from_json(json.dumps([profile()]))
    assert registry.get(None).id == "primary"
    assert registry.get("primary").base_url == "https://example.odoo.com"


def test_requires_explicit_target_for_two_profiles():
    registry = ConnectionRegistry.from_json(json.dumps([profile(), profile("other")]))
    with pytest.raises(ValueError, match="explicit connection"):
        registry.get(None)
    assert registry.get("other").id == "other"


@pytest.mark.parametrize("url", [
    "https://alice:secret@example.com",
    "http://example.odoo.com",
    "https://127.0.0.1",
    "https://localhost",
    "https://10.1.2.3",
    "https://example.com@localhost",
    "https://example.com/path",
])
def test_blocks_unsafe_urls(url):
    with pytest.raises(ValueError):
        ConnectionRegistry.from_json(json.dumps([profile(url=url)]))


def test_local_dev_accepts_loopback_http_only():
    result = ConnectionRegistry.from_json(json.dumps([profile(url="http://127.0.0.1:8069")]), allow_local=True)
    assert result.get(None).base_url == "http://127.0.0.1:8069"
    with pytest.raises(ValueError):
        ConnectionRegistry.from_json(json.dumps([profile(url="http://10.0.0.1")]), allow_local=True)


def test_secret_reference_only(monkeypatch):
    with pytest.raises(ValueError):
        ConnectionRegistry.from_json(json.dumps([profile(api_key="plaintext")]))
    monkeypatch.setenv("ODOO_KEY_PRIMARY", "supersecret-token")
    credentials = EnvironmentCredentials()
    assert credentials.get("ODOO_KEY_PRIMARY") == "supersecret-token"
    assert "supersecret-token" not in repr(ConnectionRegistry.from_json(json.dumps([profile()])))


def test_missing_secret_does_not_reveal_value(monkeypatch):
    monkeypatch.delenv("ODOO_MISSING_KEY", raising=False)
    with pytest.raises(ValueError, match="not configured"):
        EnvironmentCredentials().get("ODOO_MISSING_KEY")


def test_duplicate_connection_ids_are_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        ConnectionRegistry.from_json(json.dumps([profile(), profile()]))


def test_documented_connection_example_is_valid_and_contains_no_secret():
    guide = Path(__file__).parents[2] / "docs/operations/README.md"
    content = guide.read_text(encoding="utf-8")
    example = content.split("```json\n", 1)[1].split("```", 1)[0]
    profiles = ConnectionRegistry.from_json(example)
    assert profiles.get(None).id == "sample"
    assert not re.search(r"Bearer\s+[A-Za-z0-9_-]{16,}", content)
    assert "api_key\": " not in content


@pytest.mark.parametrize("host", ["127.1", "0x7f.1", "2130706433", "0177.0.0.1"])
def test_alternate_ip_literals_cannot_reach_loopback(host):
    with pytest.raises(ValueError):
        ConnectionRegistry.from_json(json.dumps([profile(url=f"https://{host}")]))


def test_accidental_secret_field_never_leaks_from_validation():
    with pytest.raises(ValueError) as exc:
        ConnectionRegistry.from_json(json.dumps([profile(**{"api-key": "sensitive-secret-abcdef"})]))
    assert "sensitive-secret-abcdef" not in str(exc.value)


def test_dns_private_address_is_rejected_before_connection(monkeypatch):
    import socket
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.4.5.6", 443)),
    ])
    with pytest.raises(ValueError, match="non-public"):
        verify_public_destination("https://customer.example.com")


def test_dns_public_address_is_accepted(monkeypatch):
    import socket
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
    ])
    verify_public_destination("https://customer.example.com")
