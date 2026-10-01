from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AddonInfo:
    name: str
    path: Path
    manifest: dict[str, Any]

    @property
    def depends(self) -> list[str]:
        depends = self.manifest.get("depends", []) or []
        return [str(item) for item in depends if item]


@dataclass
class FieldInfo:
    name: str
    field_type: str = ""
    comodel: str = ""
    compute: str = ""
    store: bool | None = None


@dataclass
class ModelInfo:
    model: str
    class_name: str
    file: Path
    start_line: int
    end_line: int
    parents: set[str] = field(default_factory=set)
    comodels: set[str] = field(default_factory=set)
    fields: list[FieldInfo] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    score: int = 0


@dataclass
class ContextBuild:
    selected_addons: set[str]
    ordered_addons: list[str]
    missing_addons: set[str]
    excluded_addons: set[str]
    pruned_addons: set[str]
    addon_index: dict[str, AddonInfo]
    models_by_name: dict[str, list[ModelInfo]]
    expand_models: set[str]
    related_models: set[str]
    warnings: list[str]
