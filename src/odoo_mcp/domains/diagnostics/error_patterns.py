from __future__ import annotations

from typing import Any

ERROR_PATTERNS: list[dict[str, Any]] = [
    {
        "needles": ["parseerror", "while parsing", "xmlsyntaxerror"],
        "area": "XML data or view loading",
        "cause": "Malformed XML, invalid field in a view, bad xpath, or data loaded before its dependency.",
        "docs": ["reference/backend/data", "reference/user_interface/view_architectures"],
        "repro": "Update the module with only the XML file that fails, then inspect the record and line reported by the parser.",
    },
    {
        "needles": ["external id not found", "xmlid", "not found in the system"],
        "area": "XML ID / dependency / data load order",
        "cause": "A referenced XML ID is missing, loaded later, renamed, or owned by a module missing from `depends`.",
        "docs": ["reference/backend/data", "reference/backend/module"],
        "repro": "Search for the referenced XML ID, verify the owning module is in `depends`, and check data file order.",
    },
    {
        "needles": ["accesserror", "access rights", "ir.model.access"],
        "area": "Security ACLs",
        "cause": "The user lacks model-level read/write/create/unlink access or the ACL CSV is missing/wrong.",
        "docs": ["reference/backend/security#access-rights"],
        "repro": "Reproduce as the failing user and check `security/ir.model.access.csv` plus implied groups.",
    },
    {
        "needles": ["record rules", "record rule", "due to security restrictions"],
        "area": "Record rules",
        "cause": "A row-level domain blocks access even though ACLs allow the operation.",
        "docs": ["reference/backend/security#record-rules"],
        "repro": "Reproduce as the failing user, then compare accessible records with and without each relevant rule.",
    },
    {
        "needles": ["undefinedcolumn", "column", "does not exist"],
        "area": "Database schema / field migration",
        "cause": "The database schema is not aligned with the model fields, often after a missing module update or field rename.",
        "docs": ["reference/backend/orm#fields", "reference/upgrades/upgrade_scripts#writing-upgrade-scripts"],
        "repro": "Upgrade the owning module on a copy of the database and verify whether the missing column exists after registry init.",
    },
    {
        "needles": ["undefinedtable", "relation", "does not exist"],
        "area": "Database table / module installation",
        "cause": "A model table is missing because its module is not installed, not upgraded, or `_auto`/model naming changed.",
        "docs": ["reference/backend/orm#models", "reference/backend/module"],
        "repro": "Check the model's owning module, manifest dependencies, and whether the module update created the table.",
    },
    {
        "needles": ["invalid field", "unknown field"],
        "area": "Model field / view / domain",
        "cause": "A field name in Python, XML, domain, or data does not exist on the target model for this version.",
        "docs": ["reference/backend/orm#fields", "reference/user_interface/view_architectures"],
        "repro": "Inspect the target model fields in Odoo shell and check whether a dependency module adds the field.",
    },
    {
        "needles": ["expected singleton"],
        "area": "ORM recordset handling",
        "cause": "Code assumes one record but receives multiple records; missing loop, `ensure_one()`, or batching logic.",
        "docs": ["reference/backend/orm#recordsets", "reference/backend/performance#batch-operations"],
        "repro": "Call the method with a multi-record recordset and inspect the line that dereferences a singleton-only field/method.",
    },
    {
        "needles": ["xpath", "cannot be located", "element '<xpath"],
        "area": "View inheritance",
        "cause": "An inherited view xpath no longer matches the parent architecture or the parent view dependency is wrong.",
        "docs": ["reference/user_interface/view_architectures"],
        "repro": "Open the final parent view architecture in developer mode and test the xpath against the actual XML.",
    },
    {
        "needles": ["qwebexception", "template", "t-call", "t-field"],
        "area": "QWeb report/template",
        "cause": "A template expression, field access, or template inheritance failed during rendering.",
        "docs": ["reference/frontend/qweb", "reference/backend/reports"],
        "repro": "Render the report/template with the smallest recordset that fails and inspect the template path in the traceback.",
    },
    {
        "needles": ["modulenotfounderror", "importerror", "no module named"],
        "area": "Python imports / dependencies",
        "cause": "A Python dependency or addon import is missing from the environment or manifest dependencies.",
        "docs": ["reference/backend/module"],
        "repro": "Import the module in the same Python environment used by Odoo and verify manifest dependencies.",
    },
    {
        "needles": ["owlerror", "uncaughtpromiseerror", "javascript error"],
        "area": "Odoo web / OWL frontend",
        "cause": "A frontend component, service, registry entry, asset, or template failed in the browser.",
        "docs": ["reference/frontend/owl_components", "reference/frontend/services", "reference/frontend/assets"],
        "repro": "Reproduce with browser dev tools open, check loaded asset bundle, and isolate the component/template mentioned in the stack.",
    },
]
