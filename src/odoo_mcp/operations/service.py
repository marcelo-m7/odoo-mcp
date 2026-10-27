"""Policy-protected, bounded ORM services shared by MCP tools and resources."""

from __future__ import annotations

import json
import re
from collections.abc import Callable

from .backends import OdooBackend
from .config import ConnectionConfig, ConnectionRegistry
from .errors import OperationError
from .policy import Policy


_FIELD = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$")
_AGGREGATE = re.compile(r"^[a-z][a-z0-9_]*:(?:sum|avg|min|max|count|count_distinct)$")
_ORDER = re.compile(r"^[a-z][a-z0-9_]*(?:\s+(?:asc|desc))?(?:,\s*[a-z][a-z0-9_]*(?:\s+(?:asc|desc))?)*$", re.I)
_OPS = frozenset({"=", "!=", ">", "<", ">=", "<=", "in", "not in", "like", "not like", "ilike", "not ilike", "child_of", "parent_of", "=?"})
_SAFE_DEFAULT_FIELDS = ["id", "display_name"]


def _domain(value: list[object] | None) -> list[object]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > 100:
        raise ValueError("Domain must be a list with no more than 100 terms")
    stack = 0
    for term in reversed(value):
        if isinstance(term, str) and term in ("&", "|", "!"):
            required = 1 if term == "!" else 2
            if stack < required:
                raise ValueError("Incomplete Odoo domain expression")
            if required == 2:
                stack -= 1
            continue
        if not isinstance(term, (list, tuple)) or len(term) != 3:
            raise ValueError("Malformed Odoo domain")
        name, operation, arg = term
        if not isinstance(name, str) or not _FIELD.fullmatch(name) or not isinstance(operation, str) or operation not in _OPS:
            raise ValueError("Invalid Odoo domain field/operator")
        try:
            json.dumps(arg)
        except (TypeError, ValueError) as exc:
            raise ValueError("Odoo domain contains an unserializable value") from exc
        stack += 1
    return value


def _fields(value: list[str] | None) -> list[str] | None:
    if value is None:
        return list(_SAFE_DEFAULT_FIELDS)
    if not isinstance(value, list) or not 1 <= len(value) <= 50 or any(not isinstance(x, str) or not _FIELD.fullmatch(x) for x in value):
        raise ValueError("Invalid or excessive field selection")
    return value


def _page(limit: int, offset: int = 0) -> None:
    if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or not 0 <= offset <= 10000:
        raise ValueError("Invalid pagination parameters")


class OdooService:
    def __init__(self, registry: ConnectionRegistry,
                 backend_for: Callable[[ConnectionConfig], OdooBackend], policy: Policy):
        self.registry = registry
        self.backend_for = backend_for
        self.policy = policy

    def _backend(self, model: str, action: str, connection: str | None) -> OdooBackend:
        profile = self.registry.get(connection)
        self.policy.authorize(model, action, connection=profile.id, allow_global=len(self.registry) == 1)
        return self.backend_for(profile)

    def fields_get(self, model: str, *, connection: str | None = None) -> dict[str, object]:
        data = self._backend(model, "read", connection).call(model, "fields_get")
        if not isinstance(data, dict):
            raise OperationError("invalid_response", "Odoo did not return model fields")
        return data

    def model_list(self, *, connection: str | None = None, limit: int = 100) -> list[dict[str, object]]:
        _page(limit)
        data = self._backend("ir.model", "read", connection).call(
            "ir.model", "search_read", kwargs={"domain": [], "fields": ["model", "name"], "limit": limit},
        )
        return self._list(data)

    @staticmethod
    def _list(data: object) -> list[dict[str, object]]:
        if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
            raise OperationError("invalid_response", "Odoo returned unexpected records")
        return data

    def search(self, model: str, *, domain: list[object] | None = None,
               fields: list[str] | None = None, limit: int = 50, offset: int = 0,
               order: str = "", connection: str | None = None) -> dict[str, object]:
        _page(limit, offset)
        domain = _domain(domain)
        fields = _fields(fields)
        if order and not _ORDER.fullmatch(order):
            raise ValueError("Invalid Odoo order expression")
        backend = self._backend(model, "read", connection)
        kwargs: dict[str, object] = {"domain": domain, "limit": limit, "offset": offset}
        kwargs["fields"] = fields
        if order:
            kwargs["order"] = order
        records = self._list(backend.call(model, "search_read", kwargs=kwargs))
        total = backend.call(model, "search_count", kwargs={"domain": domain})
        if type(total) is not int or total < 0:
            raise OperationError("invalid_response", "Odoo returned an invalid record count")
        return {"records": records, "total": total, "limit": limit, "offset": offset}

    def get(self, model: str, record_id: int, *, fields: list[str] | None = None,
            connection: str | None = None) -> dict[str, object]:
        if type(record_id) is not int or record_id <= 0:
            raise ValueError("Invalid record ID")
        selected = _fields(fields)
        kwargs = {"fields": selected} if selected is not None else {}
        records = self._list(self._backend(model, "read", connection).call(model, "read", ids=[record_id], kwargs=kwargs))
        if not records:
            raise OperationError("odoo_not_found", "Odoo record was not found")
        return records[0]

    def aggregate(self, model: str, *, domain: list[object] | None = None,
                  groupby: list[str], aggregates: list[str], limit: int = 50,
                  connection: str | None = None) -> list[dict[str, object]]:
        _page(limit)
        domain = _domain(domain)
        if (not isinstance(groupby, list) or not 1 <= len(groupby) <= 5 or
                any(not isinstance(f, str) or not _FIELD.fullmatch(f) for f in groupby)):
            raise ValueError("Invalid aggregate group-by fields")
        if (not isinstance(aggregates, list) or not 1 <= len(aggregates) <= 10 or
                any(not isinstance(f, str) or not _AGGREGATE.fullmatch(f) for f in aggregates)):
            raise ValueError("Invalid aggregate fields")
        data = self._backend(model, "aggregate", connection).call(
            model, "read_group", kwargs={"domain": domain, "fields": aggregates, "groupby": groupby, "limit": limit, "lazy": False},
        )
        return self._list(data)

    @staticmethod
    def _values(values: dict[str, object]) -> dict[str, object]:
        if not isinstance(values, dict) or not values or any(
            not isinstance(field, str) or not _FIELD.fullmatch(field) or "." in field
            for field in values
        ):
            raise ValueError("Invalid Odoo write field values")
        if any(type(value) not in (str, int, float, bool, type(None)) for value in values.values()):
            raise ValueError("Only scalar Odoo write values are supported in this MVP")
        try:
            json.dumps(values, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("Odoo write payload must contain JSON values") from exc
        return values

    def create(self, model: str, values: dict[str, object], *, connection: str | None = None) -> int:
        values = self._values(values)
        result = self._backend(model, "create", connection).call(model, "create", kwargs={"vals_list": [values]})
        if isinstance(result, list) and len(result) == 1 and type(result[0]) is int and result[0] > 0:
            return result[0]
        if type(result) is int and result > 0:
            return result
        raise OperationError("invalid_response", "Odoo did not return a created record ID")

    def update(self, model: str, record_id: int, values: dict[str, object], *, connection: str | None = None) -> bool:
        if type(record_id) is not int or record_id <= 0:
            raise ValueError("Invalid record ID")
        values = self._values(values)
        result = self._backend(model, "write", connection).call(model, "write", ids=[record_id], kwargs={"vals": values})
        if type(result) is not bool:
            raise OperationError("invalid_response", "Odoo did not return a write result")
        return result

    def delete(self, model: str, record_id: int, *, connection: str | None = None) -> bool:
        if type(record_id) is not int or record_id <= 0:
            raise ValueError("Invalid record ID")
        result = self._backend(model, "unlink", connection).call(model, "unlink", ids=[record_id])
        if type(result) is not bool:
            raise OperationError("invalid_response", "Odoo did not return a deletion result")
        return result
