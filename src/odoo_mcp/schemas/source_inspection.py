from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceInspectionRequest:
    path: str = ""
    query: str = ""
    scope: str = "both"
    max_files: int = 200
