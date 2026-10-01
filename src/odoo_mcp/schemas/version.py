from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VersionDetectionRequest:
    path: str = ""
    include_env: bool = True
    include_source: bool = True
    include_manifests: bool = True
    include_branch: bool = True
