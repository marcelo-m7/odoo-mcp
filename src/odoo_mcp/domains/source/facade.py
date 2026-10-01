from __future__ import annotations

from ...schemas.source_inspection import SourceInspectionRequest
from .inspection import inspect_odoo_source_content


def inspect_odoo_source(request: SourceInspectionRequest, *, env_source: str = "") -> str:
    return inspect_odoo_source_content(
        path=request.path,
        query=request.query,
        scope=request.scope,
        max_files=request.max_files,
        env_source=env_source,
    )
