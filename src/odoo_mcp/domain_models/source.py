from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ManifestSummary:
    name: str
    version: str
    path: str
    depends: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RouteInfo:
    method: str
    routes: list[str]
    auth: str = ""
    type: str = ""


@dataclass(frozen=True)
class PythonSummary:
    path: str
    source_kind: str
    classes: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
