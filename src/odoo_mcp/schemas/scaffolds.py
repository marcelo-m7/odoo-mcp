from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ModelScaffoldRequest:
    model_name: str
    model_description: str
    fields: list[dict[str, Any]]
    inherit: str = ""


@dataclass(frozen=True)
class ModuleScaffoldRequest:
    module_name: str
    display_name: str
    description: str
    author: str = "Your Company"
    category: str = "Uncategorized"
    depends: list[str] | None = None
