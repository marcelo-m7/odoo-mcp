from __future__ import annotations

from pathlib import Path

from ...runtime.state import ODOO_VERSIONS, current_version
from ...schemas.version import VersionDetectionRequest
from .local_context import configured_env_value, get_odoo_local_context_content
from .version_detection import (
    detect_version_from_branch,
    detect_version_from_env,
    detect_version_from_manifests,
    detect_version_from_source,
    format_version_evidence,
    summarize_version_evidence,
)


def detect_odoo_version(request: VersionDetectionRequest) -> str:
    evidence = []
    if request.include_env:
        evidence.extend(detect_version_from_env())
    if request.include_source:
        evidence.extend(detect_version_from_source(request.path))
    if request.include_manifests:
        evidence.extend(detect_version_from_manifests(request.path))
    if request.include_branch:
        evidence.extend(detect_version_from_branch(request.path))

    detected, confidence, versions = summarize_version_evidence(evidence)
    target = Path(request.path).expanduser() if request.path.strip() else None
    inspected = str(target) if target else configured_env_value("ODOO_SOURCE") or "environment only / no path configured"

    output = [
        "# Odoo Version Detection",
        "",
        f"Active MCP version: `{current_version['value']}`",
        f"Inspected: `{inspected}`",
        "",
    ]

    if confidence == "none":
        output.extend([
            "Result: no version detected.",
            "",
            "## Evidence",
            format_version_evidence(evidence),
            "",
            "## Next Step",
            "Set `ODOO_SOURCE`, pass an explicit `path`, or configure `ODOO_VERSION` / `DEFAULT_ODOO_VERSION`.",
        ])
        return "\n".join(output)

    if confidence == "conflict":
        output.extend([
            "Result: conflict detected.",
            f"Top candidate by evidence weight: `{detected}`",
            f"Detected candidates: {', '.join(f'`{version}`' for version in versions)}",
            "",
            "## Evidence",
            format_version_evidence(evidence),
            "",
            "## Next Step",
            "Resolve the conflicting sources, then run `set_odoo_version(...)` manually if the active MCP version should change.",
        ])
        return "\n".join(output)

    supported = detected in ODOO_VERSIONS
    output.extend([
        f"Result: `{detected}` detected with {confidence} confidence.",
        "",
        "## Evidence",
        format_version_evidence(evidence),
        "",
        "## Next Step",
    ])
    if supported:
        output.append(f"Suggested current version: `{detected}`. Run `set_odoo_version(\"{detected}\")` to apply it.")
    else:
        output.append(f"Detected `{detected}`, but this MCP currently supports docs/code generation for: {', '.join(ODOO_VERSIONS)}.")
    return "\n".join(output)


def get_odoo_local_context(include_readme_excerpt: bool = True) -> str:
    return get_odoo_local_context_content(include_readme_excerpt=include_readme_excerpt)
