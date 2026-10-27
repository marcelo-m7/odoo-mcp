from __future__ import annotations

from ...schemas.addon_context import AddonContextRequest
from .context_builder import build_odoo_addon_context


def read_odoo_addon_context(request: AddonContextRequest, *, env_source: str = "") -> str:
    return build_odoo_addon_context(
        addon=request.addon,
        addons_path=request.addons_path,
        path=request.path,
        odoo_config=request.odoo_config,
        include=request.include,
        exclude_addons=request.exclude_addons,
        no_exclude_addons=request.no_exclude_addons,
        shrink_mode=request.shrink_mode,
        expand_models=request.expand_models,
        add_expand_models=request.add_expand_models,
        rm_expand_models=request.rm_expand_models,
        expand_methods=request.expand_methods,
        auto_expand=request.auto_expand,
        context_budget_tokens=request.context_budget_tokens,
        max_files=request.max_files,
        env_source=env_source,
    )
