from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AddonContextRequest:
    addon: str
    addons_path: str = ""
    path: str = ""
    odoo_config: str = ""
    include: str = ""
    exclude_addons: list[str] | None = None
    no_exclude_addons: list[str] | None = None
    shrink_mode: str = "soft"
    expand_models: list[str] | None = None
    add_expand_models: list[str] | None = None
    rm_expand_models: list[str] | None = None
    expand_methods: list[str] | None = None
    auto_expand: bool = True
    context_budget_tokens: int | None = None
    max_files: int = 200
