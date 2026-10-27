from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VersionEvidence:
    version: str
    source: str
    value: str
    detail: str
    weight: int = 1
    supported: bool = False
