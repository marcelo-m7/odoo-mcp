from __future__ import annotations

import os
from pathlib import Path

from .redaction import redact_sensitive_text


def configured_env_value(name: str) -> str:
    return os.environ.get(name, "").strip()


def path_status(path_value: str) -> tuple[str, str]:
    if not path_value:
        return "not configured", ""
    expanded = Path(path_value).expanduser()
    if expanded.exists():
        kind = "directory" if expanded.is_dir() else "file"
        return f"configured ({kind} exists)", str(expanded)
    return "configured (path does not exist)", str(expanded)


def read_readme_excerpt(readme_path: str, max_lines: int = 40) -> str:
    if not readme_path:
        return "Not configured."
    expanded = Path(readme_path).expanduser()
    if not expanded.exists() or not expanded.is_file():
        return "Configured, but the file does not exist."
    try:
        lines = expanded.read_text(encoding="utf-8").splitlines()
    except Exception as exc:
        return f"Configured, but could not be read: {exc}"
    excerpt = "\n".join(lines[:max_lines]).strip()
    if len(lines) > max_lines:
        excerpt += f"\n... ({len(lines) - max_lines} more lines)"
    return redact_sensitive_text(excerpt) or "Configured file is empty."


def local_odoo_roots(source: Path) -> list[Path]:
    roots = [source]
    try:
        children = sorted(source.iterdir(), key=lambda path: path.name)
    except OSError:
        return roots
    for child in children:
        if child.is_dir() and ((child / "odoo-bin").exists() or child.name.startswith("odoo")):
            roots.append(child)
    return roots


def local_source_hints(source: Path | None) -> list[str]:
    if source is None:
        return ["- Set `ODOO_SOURCE=/path/to/odoo` to enable local source hints."]

    hints: list[str] = []
    for root in local_odoo_roots(source):
        for relative in ["odoo-bin", "addons", "odoo/addons"]:
            candidate = root / relative
            hints.append(f"- `{candidate}`: {'exists' if candidate.exists() else 'not found'}")

    enterprise_candidates: list[Path] = []
    for root in local_odoo_roots(source):
        try:
            enterprise_candidates.extend(sorted(root.glob("enterprise*"), key=lambda path: path.name))
        except OSError:
            continue
    if enterprise_candidates:
        for candidate in enterprise_candidates:
            kind = "directory" if candidate.is_dir() else "file"
            hints.append(f"- `{candidate}`: enterprise candidate ({kind})")
    else:
        hints.append(f"- `{source / 'enterprise'}` or `{source / 'enterprise-*'}`: not found")

    return hints


def get_odoo_local_context_content(include_readme_excerpt: bool = True) -> str:
    odoo_source = configured_env_value("ODOO_SOURCE")
    odoo_base_command = configured_env_value("ODOO_BASE_COMMAND")
    odoo_tool_readme = configured_env_value("ODOO_TOOL_README")
    source_status, source_path = path_status(odoo_source)
    readme_status, readme_path = path_status(odoo_tool_readme)
    redacted_base_command = redact_sensitive_text(odoo_base_command)

    source = Path(source_path) if source_path else None
    source_hints = local_source_hints(source)

    if odoo_base_command:
        command_hints = f"""- Module update template: `{redacted_base_command} -d <database> -u <module> --stop-after-init`
- Module install/test template: `{redacted_base_command} -d <database> -i <module> --test-enable --stop-after-init`
- Shell template: `{redacted_base_command} shell -d <database>`"""
    else:
        command_hints = "- Set `ODOO_BASE_COMMAND=\"/path/to/odoo/odoo-bin -c /path/to/odoo.conf --addons-path=/path/to/addons\"` to enable command templates."

    readme_excerpt = read_readme_excerpt(odoo_tool_readme) if include_readme_excerpt else "Readme excerpt omitted."

    return f"""# Local Odoo Tool Context

## Environment Variables

- `ODOO_SOURCE`: {source_status}{f' -> `{source_path}`' if source_path else ''}
- `ODOO_BASE_COMMAND`: {'configured' if odoo_base_command else 'not configured'}{f' -> `{redacted_base_command}`' if odoo_base_command else ''}
- `ODOO_TOOL_README`: {readme_status}{f' -> `{readme_path}`' if readme_path else ''}

## Source Hints

{chr(10).join(source_hints)}

## Command Templates

{command_hints}

## Local Tool README Excerpt

{readme_excerpt}

## Guardrails

- Use `ODOO_SOURCE` to inspect framework behavior before making version-sensitive assumptions.
- Use `ODOO_TOOL_README` to discover project-specific local commands before proposing Odoo update/test commands.
- Treat `ODOO_BASE_COMMAND` as a starting point, not permission to run database-touching commands automatically.
- Ask before running commands that update modules, install modules, start services, or touch a database.
"""
