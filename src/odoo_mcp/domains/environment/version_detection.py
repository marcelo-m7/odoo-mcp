from __future__ import annotations

import ast
from pathlib import Path
import re
from typing import Any

from ...runtime.state import ODOO_VERSIONS
from .local_context import configured_env_value, local_odoo_roots

VERSION_PATTERN = re.compile(r"(?<!\d)(\d{2}\.0)(?!\d)")


def normalize_odoo_version(value: Any) -> str:
    text = str(value).strip()
    if not text:
        return ""
    match = VERSION_PATTERN.search(text)
    if match:
        return match.group(1)
    if text.isdigit() and len(text) == 2:
        return f"{text}.0"
    return ""


def version_evidence(source: str, value: Any, detail: str, weight: int = 1) -> dict[str, Any] | None:
    version = normalize_odoo_version(value)
    if not version:
        return None
    return {
        "version": version,
        "source": source,
        "value": str(value),
        "detail": detail,
        "weight": weight,
        "supported": version in ODOO_VERSIONS,
    }


def detect_version_from_env() -> list[dict[str, Any]]:
    evidence = []
    for name in ["ODOO_VERSION", "DEFAULT_ODOO_VERSION"]:
        value = configured_env_value(name)
        item = version_evidence("environment", value, f"{name}={value}", weight=3)
        if item:
            evidence.append(item)
    return evidence


def candidate_roots(path: str = "") -> list[Path]:
    roots = []
    if path.strip():
        roots.append(Path(path).expanduser())
    source_path = configured_env_value("ODOO_SOURCE")
    if source_path:
        roots.append(Path(source_path).expanduser())

    unique = []
    seen = set()
    for root in roots:
        try:
            key = str(root.resolve())
        except OSError:
            key = str(root)
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def source_roots(path: str = "") -> list[Path]:
    roots = []
    for root in candidate_roots(path):
        roots.extend(local_odoo_roots(root) if root.exists() else [root])
    unique = []
    seen = set()
    for root in roots:
        try:
            key = str(root.resolve())
        except OSError:
            key = str(root)
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def literal_assignment(source: str, names: set[str]) -> dict[str, Any]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    values = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in names:
                try:
                    values[target.id] = ast.literal_eval(node.value)
                except (ValueError, TypeError):
                    continue
    return values


def release_file_version(release_file: Path) -> str:
    try:
        values = literal_assignment(release_file.read_text(encoding="utf-8"), {"version", "server_version", "version_info"})
    except OSError:
        return ""
    for name in ["version", "server_version"]:
        version = normalize_odoo_version(values.get(name, ""))
        if version:
            return version
    version_info = values.get("version_info")
    if isinstance(version_info, (list, tuple)) and len(version_info) >= 2:
        major, minor = version_info[0], version_info[1]
        if isinstance(major, int) and isinstance(minor, int):
            return normalize_odoo_version(f"{major}.{minor}")
    return ""


def detect_version_from_source(path: str = "") -> list[dict[str, Any]]:
    evidence = []
    for root in source_roots(path):
        for release_file in [root / "odoo" / "release.py", root / "release.py"]:
            if not release_file.exists():
                continue
            version = release_file_version(release_file)
            item = version_evidence("source release.py", version, str(release_file), weight=4)
            if item:
                evidence.append(item)
    return evidence


def manifest_version(manifest_file: Path) -> str:
    try:
        values = ast.literal_eval(manifest_file.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError, TypeError):
        return ""
    if not isinstance(values, dict):
        return ""
    return normalize_odoo_version(values.get("version", ""))


def detect_version_from_manifests(path: str = "", limit: int = 500) -> list[dict[str, Any]]:
    evidence = []
    for root in candidate_roots(path):
        if not root.is_dir():
            continue
        scanned = 0
        for manifest_file in root.rglob("__manifest__.py"):
            scanned += 1
            if scanned > limit:
                evidence.append({
                    "version": "",
                    "source": "manifest",
                    "value": "scan limit reached",
                    "detail": f"Stopped after {limit} manifests under {root}",
                    "weight": 0,
                    "supported": False,
                })
                break
            version = manifest_version(manifest_file)
            item = version_evidence("manifest", version, str(manifest_file), weight=1)
            if item:
                evidence.append(item)
    return evidence


def find_git_dir(root: Path) -> Path | None:
    current = root if root.is_dir() else root.parent
    for candidate in [current, *current.parents]:
        git_path = candidate / ".git"
        if git_path.is_dir():
            return git_path
    return None


def detect_version_from_branch(path: str = "") -> list[dict[str, Any]]:
    evidence = []
    for root in candidate_roots(path):
        git_dir = find_git_dir(root)
        if git_dir is None:
            continue
        head = git_dir / "HEAD"
        try:
            head_text = head.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        branch = head_text.removeprefix("ref: refs/heads/")
        item = version_evidence("branch", branch, f"{head}: {branch}", weight=2)
        if item:
            evidence.append(item)
    return evidence


def summarize_version_evidence(evidence: list[dict[str, Any]]) -> tuple[str, str, list[str]]:
    scores: dict[str, int] = {}
    counts: dict[str, int] = {}
    for item in evidence:
        version = item.get("version", "")
        if not version:
            continue
        scores[version] = scores.get(version, 0) + int(item.get("weight", 1))
        counts[version] = counts.get(version, 0) + 1

    versions = sorted(scores, key=lambda version: (-scores[version], version))
    if not versions:
        return "unknown", "none", []
    if len(versions) > 1:
        return versions[0], "conflict", versions

    version = versions[0]
    if scores[version] >= 4:
        confidence = "high"
    elif counts[version] >= 2 or scores[version] >= 2:
        confidence = "medium"
    else:
        confidence = "low"
    return version, confidence, versions


def format_version_evidence(evidence: list[dict[str, Any]]) -> str:
    lines = []
    for item in evidence:
        version = item.get("version", "")
        source = item.get("source", "unknown")
        detail = item.get("detail", "")
        if version:
            supported = "supported" if item.get("supported") else "unsupported by this MCP"
            lines.append(f"- `{version}` from {source}: {detail} ({supported})")
        else:
            lines.append(f"- {source}: {detail}")
    return "\n".join(lines) or "- No version evidence found."
