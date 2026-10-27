from __future__ import annotations

from ...runtime.state import ODOO_VERSIONS, current_version
from ..docs.facade import get_official_documentation_url
from .error_patterns import ERROR_PATTERNS

def explain_odoo_error(error_text: str, version: str = "", context: str = "") -> str:
    error_version = version if version in ODOO_VERSIONS else current_version["value"]
    text_lower = error_text.lower()
    matches = [
        pattern for pattern in ERROR_PATTERNS
        if any(needle in text_lower for needle in pattern["needles"])
    ]
    if not matches:
        matches = [{
            "area": "Unknown / needs reproduction",
            "cause": "No strong Odoo error pattern matched. Start by reproducing with full traceback and module update logs.",
            "docs": ["reference/backend/orm", "reference/backend/testing"],
            "repro": "Capture the complete traceback, current module being loaded, Odoo version, installed dependencies, and the exact action that triggers the error.",
        }]

    primary = matches[0]
    docs_output = []
    for doc_path in primary["docs"]:
        docs_output.append(f"- {doc_path}: {get_official_documentation_url(error_version, doc_path)}")

    secondary_output = "\n".join(
        f"- {match['area']}: {match['cause']}"
        for match in matches[1:4]
    ) or "- No secondary pattern matched."

    context_output = f"\n## Supplied Context\n\n{context}\n" if context else ""

    return f"""# Odoo Error Explanation (Odoo {error_version})

## Likely Area

{primary['area']}

## Likely Root Cause

{primary['cause']}

## Minimal Reproduction

{primary['repro']}

## What To Inspect First

- The first custom addon frame in the traceback.
- The model, XML record, field, view, or security rule named closest to the original exception.
- The manifest `depends` and data file order for the module currently loading.
- Whether the behavior changes between a fresh install and `-u module_name` upgrade.

## Secondary Matches

{secondary_output}
{context_output}
## Relevant Documentation

{chr(10).join(docs_output)}
"""
