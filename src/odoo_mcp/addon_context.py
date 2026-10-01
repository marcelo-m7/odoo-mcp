from __future__ import annotations

import ast
import configparser
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


TOKEN_FACTOR = 0.27
MAX_TEXT_FILE_BYTES = 50 * 1024
MAX_DATA_FILE_BYTES = 20 * 1024
AUTO_EXPAND_THRESHOLD = 7

FRAMEWORK_ADDONS = {
    "base",
    "web",
    "web_editor",
    "web_tour",
    "portal",
    "mail",
    "digest",
    "bus",
    "auth_signup",
    "base_setup",
    "http_routing",
    "utm",
    "uom",
    "product",
}

BLACKLIST_AUTO_EXPAND = {
    "res.users",
    "res.groups",
    "res.company",
    "res.partner",
    "mail.thread",
    "mail.activity.mixin",
    "portal.mixin",
    "ir.ui.view",
    "ir.model",
    "ir.model.fields",
    "ir.model.data",
    "ir.attachment",
    "res.config.settings",
    "utm.mixin",
}

BLACKLIST_RELATION_EXPAND = {
    "ir.attachment",
    "mail.activity.mixin",
    "mail.thread",
    "portal.mixin",
    "res.company",
    "res.currency",
    "res.partner",
    "res.partner.bank",
    "resource.calendar",
    "resource.resource",
    "sequence.mixin",
    "uom.uom",
    "utm.mixin",
}

BINARY_EXTS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".svg",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".pdf",
    ".map",
}

SHRINK_MODES = ["none", "soft", "medium", "hard", "max"]
SHRINK_MATRIX: dict[str, dict[str, str]] = {
    "none": {"T_EXP": "none", "T_OTH": "none", "D_EXP": "none", "D_REL": "none", "D_OTH": "none"},
    "soft": {"T_EXP": "none", "T_OTH": "none", "D_EXP": "none", "D_REL": "soft", "D_OTH": "max"},
    "medium": {"T_EXP": "none", "T_OTH": "soft", "D_EXP": "none", "D_REL": "max", "D_OTH": "prune"},
    "hard": {"T_EXP": "none", "T_OTH": "soft", "D_EXP": "soft", "D_REL": "max", "D_OTH": "prune"},
    "max": {"T_EXP": "none", "T_OTH": "soft", "D_EXP": "max", "D_REL": "max", "D_OTH": "prune"},
}


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


def build_odoo_addon_context(
    addon: str,
    *,
    addons_path: str = "",
    path: str = "",
    odoo_config: str = "",
    include: str = "",
    exclude_addons: list[str] | None = None,
    no_exclude_addons: list[str] | None = None,
    shrink_mode: str = "soft",
    expand_models: list[str] | None = None,
    add_expand_models: list[str] | None = None,
    rm_expand_models: list[str] | None = None,
    expand_methods: list[str] | None = None,
    auto_expand: bool = True,
    context_budget_tokens: int | None = None,
    max_files: int = 200,
    env_source: str = "",
) -> str:
    """Build a compact Odoo addon context dump without external deps."""
    requested_mode = normalize_shrink_mode(shrink_mode)
    start_index = SHRINK_MODES.index(requested_mode)
    modes_to_try = SHRINK_MODES[start_index:] if context_budget_tokens else [requested_mode]
    budget_chars = int(context_budget_tokens / TOKEN_FACTOR) if context_budget_tokens else None

    last_report = ""
    for escalation_level, mode in enumerate(modes_to_try):
        report = render_odoo_addon_context(
            addon=addon,
            addons_path=addons_path,
            path=path,
            odoo_config=odoo_config,
            include=include,
            exclude_addons=exclude_addons,
            no_exclude_addons=no_exclude_addons,
            shrink_mode=mode,
            expand_models=expand_models,
            add_expand_models=add_expand_models,
            rm_expand_models=rm_expand_models,
            expand_methods=expand_methods,
            auto_expand=auto_expand,
            max_files=max_files,
            env_source=env_source,
            escalation_level=escalation_level,
            requested_mode=requested_mode,
        )
        last_report = report
        if budget_chars is None or len(report) <= budget_chars or mode == SHRINK_MODES[-1]:
            return report
    return last_report


def render_odoo_addon_context(
    *,
    addon: str,
    addons_path: str,
    path: str,
    odoo_config: str,
    include: str,
    exclude_addons: list[str] | None,
    no_exclude_addons: list[str] | None,
    shrink_mode: str,
    expand_models: list[str] | None,
    add_expand_models: list[str] | None,
    rm_expand_models: list[str] | None,
    expand_methods: list[str] | None,
    auto_expand: bool,
    max_files: int,
    env_source: str,
    escalation_level: int,
    requested_mode: str,
) -> str:
    max_files = max(1, min(int(max_files or 200), 1000))
    include_set = parse_include(include)
    selected_addons, roots, root_warnings = resolve_inputs(addon, path, addons_path, odoo_config, env_source)
    addon_index = scan_addons(roots)

    build = prepare_context_build(
        selected_addons=selected_addons,
        addon_index=addon_index,
        exclude_addons=exclude_addons,
        no_exclude_addons=no_exclude_addons,
        expand_models=expand_models,
        add_expand_models=add_expand_models,
        rm_expand_models=rm_expand_models,
        auto_expand=auto_expand,
    )
    build.warnings.extend(root_warnings)
    if not roots:
        build.warnings.append("No addons path candidates found. Pass `addons_path`, `path`, `odoo_config`, or configure `ODOO_SOURCE`.")
    if not addon_index:
        build.warnings.append("No Odoo addons found in the resolved path candidates.")

    file_sections: list[str] = []
    scanned_files = 0
    skipped_by_limit = 0
    expand_method_set = set(parse_list(expand_methods))
    for addon_name in build.ordered_addons:
        if addon_name in build.pruned_addons:
            continue
        addon_info = build.addon_index.get(addon_name)
        if not addon_info:
            continue
        for file_path in select_addon_files(addon_info.path, include_set):
            if scanned_files >= max_files:
                skipped_by_limit += 1
                continue
            scanned_files += 1
            content = render_file_content(
                file_path=file_path,
                addon_info=addon_info,
                selected_addons=build.selected_addons,
                shrink_mode=shrink_mode,
                expand_models=build.expand_models,
                related_models=build.related_models,
                expand_methods=expand_method_set,
            )
            if content is not None:
                file_sections.append(f"# FILEPATH: {display_path(file_path)}\n{content.rstrip()}\n")

    parts = [
        "# Odoo Addon Context",
        "",
        f"Targets: {format_inline_list(sorted(build.selected_addons))}",
        f"Requested shrink mode: `{requested_mode}`",
        f"Effective shrink mode: `{shrink_mode}`",
        f"Budget escalation level: `{escalation_level}`",
        f"Addons inspected: {format_inline_list(build.ordered_addons)}",
        f"Path candidates: {format_inline_list(str(root) for root in roots)}",
        f"Files emitted: `{len(file_sections)}`",
        "",
        "## Dependency Map",
        *format_dependency_map(build),
        "",
        "## Expansion Map",
        f"Expanded models: {format_inline_list(sorted(build.expand_models))}",
        f"Related models: {format_inline_list(sorted(build.related_models - build.expand_models))}",
        f"Expanded methods: {format_inline_list(sorted(expand_method_set))}",
        "",
        "## Schema Map",
        *format_schema_map(build.models_by_name),
        "",
        "## Warnings",
        *(f"- {warning}" for warning in build.warnings[:30]),
    ]
    if not build.warnings:
        parts.append("- None")
    if skipped_by_limit:
        parts.append(f"- Files skipped by `max_files`: {skipped_by_limit}")
    parts.extend(["", "## Source Dump", ""])
    parts.extend(file_sections or ["No source files emitted."])

    report = "\n".join(parts).rstrip() + "\n"
    estimated_tokens = int(len(report) * TOKEN_FACTOR)
    summary = f"\n## Context Size\n\n- Characters: `{len(report)}`\n- Estimated tokens: `{estimated_tokens}`\n"
    return report + summary


def prepare_context_build(
    *,
    selected_addons: set[str],
    addon_index: dict[str, AddonInfo],
    exclude_addons: list[str] | None,
    no_exclude_addons: list[str] | None,
    expand_models: list[str] | None,
    add_expand_models: list[str] | None,
    rm_expand_models: list[str] | None,
    auto_expand: bool,
) -> ContextBuild:
    warnings: list[str] = []
    ordered_addons, missing_addons = resolve_dependency_order(selected_addons, addon_index)
    if missing_addons:
        warnings.append(f"Missing addons: {', '.join(sorted(missing_addons))}")

    excluded = set(FRAMEWORK_ADDONS)
    excluded.update(parse_list(exclude_addons))
    excluded.difference_update(parse_list(no_exclude_addons))
    excluded.difference_update(selected_addons)
    pruned = {name for name in ordered_addons if name in excluded}

    models_by_name = discover_models(ordered_addons, addon_index, pruned)
    explicit_expand = set(parse_list(expand_models))
    expand_set = set(explicit_expand)
    if auto_expand and not explicit_expand:
        expand_set.update(auto_expand_models(selected_addons, models_by_name))
    expand_set.update(parse_list(add_expand_models))
    expand_set = enrich_parent_child_models(expand_set, set(models_by_name))
    expand_set = expand_parents_recursively(expand_set, models_by_name)
    related_set = resolve_related_models(expand_set, models_by_name)
    removals = set(parse_list(rm_expand_models))
    expand_set.difference_update(removals)
    related_set.difference_update(removals)

    return ContextBuild(
        selected_addons=selected_addons,
        ordered_addons=ordered_addons,
        missing_addons=missing_addons,
        excluded_addons=excluded,
        pruned_addons=pruned,
        addon_index=addon_index,
        models_by_name=models_by_name,
        expand_models=expand_set,
        related_models=expand_set | related_set,
        warnings=warnings,
    )


def resolve_inputs(
    addon: str,
    path: str,
    addons_path: str,
    odoo_config: str,
    env_source: str,
) -> tuple[set[str], list[Path], list[str]]:
    selected: set[str] = set()
    roots: list[Path] = []
    warnings: list[str] = []

    def add_root(candidate: Path) -> None:
        expanded = candidate.expanduser()
        try:
            resolved = expanded.resolve()
        except OSError:
            resolved = expanded
        if resolved not in roots and resolved.is_dir():
            roots.append(resolved)

    for item in parse_csv(addon):
        candidate = Path(item).expanduser()
        if candidate.is_dir() and (candidate / "__manifest__.py").is_file():
            selected.add(candidate.name)
            add_root(candidate.parent)
        elif candidate.is_dir():
            direct_addons = [child.name for child in safe_iterdir(candidate) if (child / "__manifest__.py").is_file()]
            if direct_addons:
                selected.update(direct_addons)
                add_root(candidate)
            else:
                selected.add(item)
        else:
            selected.add(item)

    if path.strip():
        path_obj = Path(path).expanduser()
        if path_obj.is_dir() and (path_obj / "__manifest__.py").is_file():
            add_root(path_obj.parent)
        elif path_obj.is_dir():
            add_root(path_obj)
        else:
            warnings.append(f"Path does not exist or is not a directory: {path_obj}")

    for raw_root in parse_csv(addons_path):
        add_root(Path(raw_root))

    for config_root in read_addons_path_from_config(odoo_config):
        add_root(config_root)

    for env_root in env_addons_roots(env_source or os.environ.get("ODOO_SOURCE", "")):
        add_root(env_root)

    return selected, roots, warnings


def scan_addons(roots: list[Path]) -> dict[str, AddonInfo]:
    addons: dict[str, AddonInfo] = {}
    for root in roots:
        candidates = [root] if (root / "__manifest__.py").is_file() else safe_iterdir(root)
        for candidate in candidates:
            manifest_file = candidate / "__manifest__.py"
            if not candidate.is_dir() or not manifest_file.is_file():
                continue
            manifest = read_manifest(manifest_file)
            if manifest is not None and candidate.name not in addons:
                addons[candidate.name] = AddonInfo(name=candidate.name, path=candidate.resolve(), manifest=manifest)
    return addons


def resolve_dependency_order(selected: set[str], addon_index: dict[str, AddonInfo]) -> tuple[list[str], set[str]]:
    ordered: list[str] = []
    missing: set[str] = set()
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(addon_name: str) -> None:
        if addon_name in visited:
            return
        if addon_name in visiting:
            return
        addon_info = addon_index.get(addon_name)
        if not addon_info:
            missing.add(addon_name)
            return
        visiting.add(addon_name)
        for dependency in addon_info.depends:
            visit(dependency)
        visiting.remove(addon_name)
        visited.add(addon_name)
        ordered.append(addon_name)

    for addon_name in sorted(selected):
        visit(addon_name)
    return ordered, missing


def discover_models(ordered_addons: list[str], addon_index: dict[str, AddonInfo], pruned: set[str]) -> dict[str, list[ModelInfo]]:
    models: dict[str, list[ModelInfo]] = {}
    for addon_name in ordered_addons:
        if addon_name in pruned:
            continue
        addon_info = addon_index.get(addon_name)
        if not addon_info:
            continue
        for file_path in model_python_files(addon_info.path):
            try:
                source = file_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for model in extract_models_from_source(source, file_path):
                models.setdefault(model.model, []).append(model)
    return models


def model_python_files(addon_path: Path) -> list[Path]:
    files: list[Path] = []
    for relative_root in ["models", "wizard", "wizards", "."]:
        root = addon_path if relative_root == "." else addon_path / relative_root
        if not root.is_dir():
            continue
        pattern = "*.py" if relative_root == "." else "**/*.py"
        for file_path in sorted(root.glob(pattern)):
            if file_path.is_file() and "__pycache__" not in file_path.parts and not is_trivial_init_py(file_path):
                files.append(file_path.resolve())
    return unique_paths(files)


def extract_models_from_source(source: str, file_path: Path) -> list[ModelInfo]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    models: list[ModelInfo] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        model_names, parents = model_names_from_class(node)
        if not model_names:
            continue
        fields = fields_from_class(node)
        methods = [stmt.name for stmt in node.body if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef))]
        comodels = {field.comodel for field in fields if field.comodel}
        line_count = max(0, (node.end_lineno or node.lineno) - node.lineno + 1)
        score = len(fields) + len(methods) * 3 + (line_count // 10) * 2
        for model_name in model_names:
            models.append(
                ModelInfo(
                    model=model_name,
                    class_name=node.name,
                    file=file_path.resolve(),
                    start_line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    parents=set(parents) - {model_name},
                    comodels=set(comodels),
                    fields=fields,
                    methods=methods,
                    score=score,
                )
            )
    return models


def model_names_from_class(node: ast.ClassDef) -> tuple[set[str], set[str]]:
    model_name = ""
    inherits: set[str] = set()
    delegation_parents: set[str] = set()
    for stmt in node.body:
        if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
            continue
        target = stmt.targets[0].id
        if target == "_name":
            model_name = literal_string(stmt.value)
        elif target == "_inherit":
            inherits.update(literal_string_list(stmt.value))
        elif target == "_inherits" and isinstance(stmt.value, ast.Dict):
            for key in stmt.value.keys:
                value = literal_string(key) if key else ""
                if value:
                    delegation_parents.add(value)
    if model_name:
        return {model_name}, inherits | delegation_parents
    return set(inherits), inherits | delegation_parents


def fields_from_class(node: ast.ClassDef) -> list[FieldInfo]:
    fields: list[FieldInfo] = []
    for stmt in node.body:
        if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
            continue
        field_name = stmt.targets[0].id
        if field_name.startswith("_"):
            continue
        call = stmt.value
        if not is_fields_call(call):
            continue
        field_type = call.func.attr if isinstance(call.func, ast.Attribute) else ""
        fields.append(
            FieldInfo(
                name=field_name,
                field_type=field_type,
                comodel=field_comodel(call, field_type),
                compute=field_keyword_string(call, "compute"),
                store=field_keyword_bool(call, "store"),
            )
        )
    return fields


def auto_expand_models(selected_addons: set[str], models_by_name: dict[str, list[ModelInfo]]) -> set[str]:
    expanded: set[str] = set()
    selected_paths = set(selected_addons)
    for model_name, entries in models_by_name.items():
        if model_name in BLACKLIST_AUTO_EXPAND:
            continue
        for info in entries:
            addon_name = addon_name_from_model_file(info.file)
            if addon_name in selected_paths and info.score >= AUTO_EXPAND_THRESHOLD:
                expanded.add(model_name)
                break
    return expanded


def addon_name_from_model_file(file_path: Path) -> str:
    parts = file_path.parts
    for marker in ("models", "wizard", "wizards", "controllers"):
        if marker in parts:
            index = parts.index(marker)
            if index > 0:
                return parts[index - 1]
    if len(parts) >= 2:
        return parts[-2]
    return ""


def enrich_parent_child_models(expand_set: set[str], discovered_models: set[str]) -> set[str]:
    enriched = set(expand_set)
    for model_name in list(expand_set):
        if model_name.endswith(".line"):
            parent = model_name[:-5]
            if parent in discovered_models and parent not in BLACKLIST_AUTO_EXPAND:
                enriched.add(parent)
        else:
            child = f"{model_name}.line"
            if child in discovered_models and child not in BLACKLIST_AUTO_EXPAND:
                enriched.add(child)
    return enriched


def expand_parents_recursively(expand_set: set[str], models_by_name: dict[str, list[ModelInfo]]) -> set[str]:
    result = set(expand_set)
    queue = list(expand_set)
    while queue:
        current = queue.pop(0)
        for info in models_by_name.get(current, []):
            for parent in info.parents:
                if parent and parent not in result and parent not in BLACKLIST_AUTO_EXPAND:
                    result.add(parent)
                    queue.append(parent)
    return result


def resolve_related_models(expand_set: set[str], models_by_name: dict[str, list[ModelInfo]]) -> set[str]:
    related: set[str] = set()
    for model_name in expand_set:
        for info in models_by_name.get(model_name, []):
            related.update(comodel for comodel in info.comodels if comodel not in BLACKLIST_RELATION_EXPAND)
    return related - expand_set


def select_addon_files(addon_path: Path, includes: set[str]) -> list[Path]:
    files: list[Path] = []
    manifest = addon_path / "__manifest__.py"
    if manifest.is_file():
        files.append(manifest.resolve())
    files.extend(readme_files(addon_path))
    if "model" in includes:
        files.extend(model_python_files(addon_path))
    if "controller" in includes:
        files.extend(glob_text_files(addon_path / "controllers", [".py"]))
    if "view" in includes:
        files.extend(glob_text_files(addon_path / "views", [".xml"]))
    if "wizard" in includes:
        files.extend(glob_text_files(addon_path / "wizard", [".py", ".xml"]))
        files.extend(glob_text_files(addon_path / "wizards", [".py", ".xml"]))
    if "report" in includes:
        files.extend(glob_text_files(addon_path / "report", [".py", ".xml"]))
        files.extend(glob_text_files(addon_path / "reports", [".py", ".xml"]))
    if "data" in includes:
        files.extend(glob_text_files(addon_path / "data", [".xml", ".csv"]))
    if "security" in includes:
        files.extend(glob_text_files(addon_path / "security", [".xml", ".csv"]))
    if "static" in includes:
        files.extend(glob_text_files(addon_path / "static", [".js", ".xml", ".scss", ".css"]))
    if "test" in includes:
        files.extend(glob_text_files(addon_path / "tests", [".py", ".xml", ".csv"]))
    return unique_paths(files)


def render_file_content(
    *,
    file_path: Path,
    addon_info: AddonInfo,
    selected_addons: set[str],
    shrink_mode: str,
    expand_models: set[str],
    related_models: set[str],
    expand_methods: set[str],
) -> str | None:
    if file_path.suffix.lower() in BINARY_EXTS:
        return None
    try:
        source = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    limit = MAX_DATA_FILE_BYTES if file_path.suffix.lower() in {".csv", ".xml"} else MAX_TEXT_FILE_BYTES
    if len(source) > limit and file_path.suffix.lower() != ".py":
        source = source[:limit] + f"\n\n# ... truncated by odoo-dev-mcp (size > {limit} bytes) ...\n"
    if file_path.suffix.lower() != ".py" or file_path.name == "__manifest__.py":
        if file_path.name == "__manifest__.py" and addon_info.name not in selected_addons and shrink_mode != "none":
            return shrink_manifest(source)
        return source

    file_models = {info.model for info in extract_models_from_source(source, file_path)}
    target = addon_info.name in selected_addons
    expanded = bool(file_models & expand_models)
    related = bool(file_models & related_models)
    if target:
        category = "T_EXP" if expanded else "T_OTH"
    else:
        category = "D_EXP" if expanded else "D_REL" if related else "D_OTH"
    file_shrink = SHRINK_MATRIX[shrink_mode][category]
    return shrink_python_source(source, file_path, file_shrink, expand_models, related_models, expand_methods)


def shrink_manifest(source: str) -> str:
    try:
        manifest = ast.literal_eval(source)
    except (SyntaxError, ValueError, TypeError):
        return source
    if not isinstance(manifest, dict):
        return source
    keep = {"name", "summary", "depends", "external_dependencies", "pre_init_hook", "post_init_hook", "uninstall_hook", "data"}
    compact = {key: manifest[key] for key in sorted(keep) if key in manifest}
    return repr(compact)


def shrink_python_source(
    source: str,
    file_path: Path,
    shrink_level: str,
    expand_models: set[str],
    related_models: set[str],
    expand_methods: set[str],
) -> str:
    if shrink_level == "none":
        return strip_leading_comments(source)
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source

    lines = source.splitlines()
    parts: list[str] = []
    method_selectors = parse_method_selectors(expand_methods)
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if shrink_level in {"none", "soft"}:
                append_segment(parts, lines, node)
            continue
        if isinstance(node, ast.ClassDef):
            parts.extend(shrink_class(node, lines, expand_models, related_models, method_selectors, shrink_level))
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if shrink_level == "none":
                append_segment(parts, lines, node)
            elif shrink_level == "soft":
                parts.extend(function_stub(node, lines, ""))
            continue
        if isinstance(node, ast.Assign) and shrink_level in {"none", "soft"}:
            append_segment(parts, lines, node)
    return "\n".join(part for part in parts if part is not None).rstrip() + "\n"


def shrink_class(
    node: ast.ClassDef,
    lines: list[str],
    expand_models: set[str],
    related_models: set[str],
    method_selectors: dict[str, set[str]],
    shrink_level: str,
) -> list[str]:
    model_names, _parents = model_names_from_class(node)
    if model_names & expand_models:
        class_level = "none"
    elif model_names & related_models and shrink_level == "prune":
        class_level = "max"
    else:
        class_level = shrink_level

    selected_methods = set()
    for model_name in model_names:
        selected_methods.update(method_selectors.get(model_name, set()))
    selected_methods = method_closure(node, selected_methods)
    if class_level == "none" and not selected_methods:
        return [segment(lines, node.lineno, node.end_lineno or node.lineno), ""]

    output = [class_header(node, lines)]
    emitted_body = False
    field_names: list[str] = []
    computed_names: list[str] = []
    for stmt in node.body:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            name = stmt.targets[0].id
            if name in {"_name", "_inherit", "_inherits", "_description"}:
                output.append(indent_segment(segment(lines, stmt.lineno, stmt.end_lineno or stmt.lineno), "    "))
                emitted_body = True
            elif is_fields_call(stmt.value):
                field = fields_from_assignment(stmt)
                if class_level in {"soft", "hard"}:
                    output.append(indent_segment(segment(lines, stmt.lineno, stmt.end_lineno or stmt.lineno), "    "))
                    emitted_body = True
                elif class_level == "max" and field.comodel and field.comodel in related_models:
                    output.append(f"    {field.name} = fields.{field.field_type}({field.comodel!r})")
                    emitted_body = True
                elif class_level in {"max", "prune"}:
                    if field.compute:
                        computed_names.append(f"{field.name} ({field.compute})")
                    else:
                        field_names.append(field.name)
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if stmt.name in selected_methods or class_level == "none":
                output.append(indent_segment(segment(lines, stmt.lineno, stmt.end_lineno or stmt.lineno), "    "))
                emitted_body = True
            elif class_level == "soft":
                output.extend(function_stub(stmt, lines, "    "))
                emitted_body = True
            elif class_level == "hard":
                continue
    if class_level == "max":
        if field_names:
            output.append(f"    # Shrunk fields: {', '.join(field_names[:40])}")
            emitted_body = True
        if computed_names:
            output.append(f"    # Shrunk computed fields: {', '.join(computed_names[:40])}")
            emitted_body = True
    if not emitted_body:
        output.append("    pass  # shrunk")
    output.append("")
    return output


def fields_from_assignment(stmt: ast.Assign) -> FieldInfo:
    target = stmt.targets[0]
    name = target.id if isinstance(target, ast.Name) else ""
    call = stmt.value if isinstance(stmt.value, ast.Call) else ast.Call(func=ast.Name(id="", ctx=ast.Load()), args=[], keywords=[])
    field_type = call.func.attr if isinstance(call.func, ast.Attribute) else ""
    return FieldInfo(
        name=name,
        field_type=field_type,
        comodel=field_comodel(call, field_type),
        compute=field_keyword_string(call, "compute"),
        store=field_keyword_bool(call, "store"),
    )


def function_stub(node: ast.FunctionDef | ast.AsyncFunctionDef, lines: list[str], indent: str) -> list[str]:
    start = node.lineno
    body_start = node.body[0].lineno if node.body else node.lineno + 1
    header = segment(lines, start, max(start, body_start - 1)).strip("\n")
    output = [indent_segment(header, indent)]
    output.append(f"{indent}{' ' * 4}pass  # shrunk (lines {node.lineno}-{node.end_lineno or node.lineno})")
    return output


def class_header(node: ast.ClassDef, lines: list[str]) -> str:
    body_start = node.body[0].lineno if node.body else node.lineno + 1
    return segment(lines, node.lineno, max(node.lineno, body_start - 1)).strip("\n")


def method_closure(node: ast.ClassDef, seed_methods: set[str]) -> set[str]:
    if not seed_methods:
        return set()
    graph: dict[str, set[str]] = {}
    for stmt in node.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            graph[stmt.name] = called_methods(stmt)
    closure = set(seed_methods)
    stack = list(seed_methods)
    while stack:
        current = stack.pop()
        for called in graph.get(current, set()):
            if called in graph and called not in closure:
                closure.add(called)
                stack.append(called)
    return closure


def called_methods(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    calls: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call) or not isinstance(child.func, ast.Attribute):
            continue
        receiver = child.func.value
        if isinstance(receiver, ast.Name) and receiver.id == "self":
            calls.add(child.func.attr)
        elif isinstance(receiver, ast.Call) and isinstance(receiver.func, ast.Name) and receiver.func.id == "super":
            calls.add(child.func.attr)
    return calls


def parse_method_selectors(values: set[str]) -> dict[str, set[str]]:
    selectors: dict[str, set[str]] = {}
    for value in values:
        if "." not in value:
            continue
        model_name, method_name = value.rsplit(".", 1)
        if model_name and method_name:
            selectors.setdefault(model_name, set()).add(method_name)
    return selectors


def format_dependency_map(build: ContextBuild) -> list[str]:
    if not build.ordered_addons:
        return ["- None"]
    lines: list[str] = []
    for addon_name in build.ordered_addons:
        addon_info = build.addon_index.get(addon_name)
        status = "pruned" if addon_name in build.pruned_addons else "included"
        depends = addon_info.depends if addon_info else []
        lines.append(f"- `{addon_name}` ({status}) depends={depends}")
    return lines


def format_schema_map(models_by_name: dict[str, list[ModelInfo]]) -> list[str]:
    if not models_by_name:
        return ["- None"]
    lines: list[str] = []
    for model_name in sorted(models_by_name)[:80]:
        entries = models_by_name[model_name]
        fields = sorted({field.name for entry in entries for field in entry.fields})
        methods = sorted({method for entry in entries for method in entry.methods})
        parents = sorted({parent for entry in entries for parent in entry.parents})
        comodels = sorted({comodel for entry in entries for comodel in entry.comodels})
        locations = ", ".join(f"{display_path(entry.file)}:{entry.start_line}-{entry.end_line}" for entry in entries[:4])
        lines.append(f"- `{model_name}`: files={locations}")
        if parents:
            lines.append(f"  parents: {', '.join(parents[:12])}")
        if comodels:
            lines.append(f"  relations: {', '.join(comodels[:12])}")
        if fields:
            lines.append(f"  fields: {', '.join(fields[:30])}")
        if methods:
            lines.append(f"  methods: {', '.join(methods[:20])}")
    if len(models_by_name) > 80:
        lines.append(f"- ... {len(models_by_name) - 80} more models omitted")
    return lines


def parse_include(include: str) -> set[str]:
    includes = {"model"}
    requested = set(parse_csv(include))
    if "all" in requested:
        includes.update({"view", "wizard", "data", "report", "controller", "security", "static", "test"})
    else:
        includes.update(requested)
    return includes


def normalize_shrink_mode(value: str) -> str:
    mode = (value or "soft").strip().lower()
    return mode if mode in SHRINK_MODES else "soft"


def read_manifest(manifest_file: Path) -> dict[str, Any] | None:
    try:
        value = ast.literal_eval(manifest_file.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError, TypeError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


def read_addons_path_from_config(odoo_config: str) -> list[Path]:
    if not odoo_config.strip():
        return []
    config_path = Path(odoo_config).expanduser()
    if not config_path.is_file():
        return []
    parser = configparser.ConfigParser()
    try:
        parser.read(config_path)
    except configparser.Error:
        return []
    value = parser.get("options", "addons_path", fallback="")
    return [Path(item.strip()).expanduser() for item in value.split(",") if item.strip()]


def env_addons_roots(env_source: str) -> list[Path]:
    roots: list[Path] = []
    source = Path(env_source).expanduser() if env_source.strip() else None
    if source and source.is_dir():
        candidates = [source, source / "addons", source / "odoo" / "addons", source / "custom_addons"]
        for child in safe_iterdir(source):
            if child.is_dir() and ((child / "odoo-bin").exists() or child.name.startswith("odoo")):
                candidates.extend([child / "addons", child / "odoo" / "addons"])
        roots.extend(path for path in candidates if path.is_dir())
    env_addons_path = os.environ.get("ODOO_ADDONS_PATH", "")
    roots.extend(Path(item).expanduser() for item in parse_csv(env_addons_path))
    return roots


def is_trivial_init_py(file_path: Path) -> bool:
    if file_path.name != "__init__.py":
        return False
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return False
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("import ") or stripped.startswith("from "):
            continue
        return False
    return True


def readme_files(addon_path: Path) -> list[Path]:
    files: list[Path] = []
    for relative in [
        "README.md",
        "README.rst",
        "readme/DESCRIPTION.md",
        "readme/DESCRIPTION.rst",
        "readme/USAGE.md",
        "readme/USAGE.rst",
    ]:
        candidate = addon_path / relative
        if candidate.is_file():
            files.append(candidate.resolve())
    return files


def glob_text_files(root: Path, suffixes: list[str]) -> list[Path]:
    if not root.is_dir():
        return []
    files: list[Path] = []
    for file_path in sorted(root.rglob("*")):
        if file_path.is_file() and file_path.suffix.lower() in suffixes and "__pycache__" not in file_path.parts:
            files.append(file_path.resolve())
    return files


def is_fields_call(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "fields"


def field_comodel(call: ast.Call, field_type: str) -> str:
    if field_type in {"Many2one", "One2many", "Many2many"}:
        for arg in call.args:
            value = literal_string(arg)
            if value:
                return value
            break
    return field_keyword_string(call, "comodel_name")


def field_keyword_string(call: ast.Call, name: str) -> str:
    for keyword in call.keywords:
        if keyword.arg == name:
            return literal_string(keyword.value)
    return ""


def field_keyword_bool(call: ast.Call, name: str) -> bool | None:
    for keyword in call.keywords:
        if keyword.arg == name and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, bool):
            return keyword.value.value
    return None


def literal_string(node: ast.AST | None) -> str:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else ""


def literal_string_list(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return [literal_string(item) for item in node.elts if literal_string(item)]
    return []


def strip_leading_comments(source: str) -> str:
    return re.sub(r"^(?:#.*\n)+", "", source)


def segment(lines: list[str], start: int, end: int) -> str:
    return "\n".join(lines[max(0, start - 1):end])


def append_segment(parts: list[str], lines: list[str], node: ast.AST) -> None:
    parts.append(segment(lines, node.lineno, getattr(node, "end_lineno", node.lineno) or node.lineno))


def indent_segment(text: str, indent: str) -> str:
    return "\n".join(indent + line.strip() if line.strip() else "" for line in text.splitlines())


def parse_csv(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def parse_list(values: list[str] | None) -> list[str]:
    items: list[str] = []
    for value in values or []:
        items.extend(parse_csv(str(value)))
    return items


def unique_paths(paths: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


def safe_iterdir(path: Path) -> list[Path]:
    try:
        return sorted(path.iterdir(), key=lambda item: item.name)
    except OSError:
        return []


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd()))
    except (OSError, ValueError):
        return str(path)


def format_inline_list(values: Any) -> str:
    values_list = list(values)
    if not values_list:
        return "`<none>`"
    return ", ".join(f"`{value}`" for value in values_list)
