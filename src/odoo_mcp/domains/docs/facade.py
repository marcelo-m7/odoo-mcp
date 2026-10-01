from __future__ import annotations

from pathlib import Path
from typing import Any

from ...runtime.paths import DOCS_BASE_PATH, ODOO_DOCS_BASE_URL
from ...runtime.state import ODOO_VERSIONS, current_version
from .catalog import REFERENCE_TOPICS, TOPIC_SHORTCUTS

DEVELOPER_DOC_PREFIXES = ("reference/", "howtos/", "tutorials/")

def get_all_rst_files(version: str) -> list[tuple[Path, str]]:
    """Return local RST files if present. Kept for backward-compatible tests/imports."""
    version_path = DOCS_BASE_PATH / version
    if not version_path.exists():
        return []

    files = []
    for rst_file in version_path.rglob("*.rst"):
        relative = rst_file.relative_to(version_path)
        uri_path = str(relative).replace("\\", "/").removesuffix(".rst")
        files.append((rst_file, uri_path))

    return files


def normalize_reference_path(path: str = "") -> str:
    clean_path = path.strip().strip("/")
    clean_path = clean_path.split("#", 1)[0].split("?", 1)[0]
    clean_path = clean_path.removesuffix(".html").removesuffix(".rst")

    if clean_path in {"", "reference", "developer", "developer/reference"}:
        return ""
    if clean_path.startswith("developer/"):
        clean_path = clean_path.removeprefix("developer/")
    if clean_path == "reference":
        return ""
    if not clean_path.startswith(DEVELOPER_DOC_PREFIXES):
        clean_path = f"reference/{clean_path}"

    return clean_path


def get_reference_fragment(path: str = "") -> str:
    if "#" not in path:
        return ""
    return path.split("#", 1)[1].split("?", 1)[0].strip()


def get_reference_target(path: str = "") -> str:
    reference_path = normalize_reference_path(path)
    fragment = get_reference_fragment(path)
    if fragment:
        return f"{reference_path}#{fragment}" if reference_path else f"#{fragment}"
    return reference_path


def get_all_reference_topics() -> list[dict[str, Any]]:
    return REFERENCE_TOPICS + TOPIC_SHORTCUTS


def get_official_documentation_url(version: str, path: str = "") -> str:
    reference_path = normalize_reference_path(path)
    fragment = get_reference_fragment(path)
    suffix = f"#{fragment}" if fragment else ""
    if not reference_path:
        return f"{ODOO_DOCS_BASE_URL}/{version}/developer/reference.html{suffix}"
    return f"{ODOO_DOCS_BASE_URL}/{version}/developer/{reference_path}.html{suffix}"


def get_reference_topics(version: str) -> list[dict[str, str]]:
    return [
        {
            "section": topic["section"],
            "title": topic["title"],
            "path": topic["path"],
            "url": get_official_documentation_url(version, topic["path"]),
        }
        for topic in get_all_reference_topics()
    ]


def find_reference_topic(path: str) -> dict[str, Any] | None:
    reference_target = get_reference_target(path)
    reference_path = normalize_reference_path(path)
    for topic in get_all_reference_topics():
        if get_reference_target(topic["path"]) == reference_target:
            return topic
    for topic in get_all_reference_topics():
        if normalize_reference_path(topic["path"]) == reference_path:
            return topic
    return None



def get_documentation_index(version: str) -> str:
    if version not in ODOO_VERSIONS:
        return f"Error: Unknown Odoo version {version}. Available: {', '.join(ODOO_VERSIONS)}"

    content = f"# Odoo {version} Official Developer Reference\n\n"
    content += f"Current development version: {current_version['value']}\n\n"
    content += f"Primary reference: {get_official_documentation_url(version)}\n\n"
    content += "This MCP server points to official Odoo documentation instead of vendoring documentation content.\n\n"

    current_section = ""
    for topic in get_reference_topics(version):
        if topic["section"] != current_section:
            current_section = topic["section"]
            content += f"\n## {current_section}\n\n"
        path = topic["path"] or "reference"
        content += f"- {topic['title']}: {topic['url']} (`{path}`)\n"

    return content


def get_documentation_content(version: str, path: str) -> str:
    if version not in ODOO_VERSIONS:
        return f"Error: Unknown Odoo version {version}"

    topic = find_reference_topic(path)
    url = get_official_documentation_url(version, path)
    title = topic["title"] if topic else normalize_reference_path(path) or "Developer Reference"

    content = f"# {title} (Odoo {version})\n\n"
    content += f"Official documentation: {url}\n\n"
    content += "Use the official page as the source of truth for this version. "
    content += "This server intentionally returns stable documentation links rather than stale local copies.\n"

    if topic:
        keywords = ", ".join(topic.get("keywords", []))
        content += f"\nRelated keywords: {keywords}\n"

    return content


def get_documentation_url(path: str = "", version: str = "") -> str:
    search_version = version if version and version in ODOO_VERSIONS else current_version["value"]
    url = get_official_documentation_url(search_version, path)
    reference_path = normalize_reference_path(path) or "reference"
    return f"Official Odoo {search_version} documentation for `{reference_path}`: {url}"


def search_documentation(query: str, version: str = "") -> str:
    search_version = version if version and version in ODOO_VERSIONS else current_version["value"]

    results = []
    query_lower = query.lower()

    for topic in get_all_reference_topics():
        searchable = " ".join([
            topic["section"],
            topic["title"],
            topic["path"],
            " ".join(topic.get("keywords", [])),
        ]).lower()
        if query_lower in searchable:
            results.append(topic)

    if not results:
        return (
            f"No catalog results found for '{query}' in Odoo {search_version}.\n\n"
            f"Start from the official developer reference: {get_official_documentation_url(search_version)}"
        )

    output = f"Official Odoo {search_version} documentation links for '{query}':\n\n"
    for result in results[:10]:
        output += f"## {result['title']}\n"
        output += f"Section: {result['section']}\n"
        output += f"Path: `{result['path'] or 'reference'}`\n"
        output += f"Keywords: {', '.join(result.get('keywords', []))}\n"
        output += f"URL: {get_official_documentation_url(search_version, result['path'])}\n\n"

    return output
