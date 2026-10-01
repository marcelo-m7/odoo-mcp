from __future__ import annotations

from ...runtime.state import ODOO_VERSIONS, current_version
from ...utils.formatting import normalized_string_list
from ..docs.facade import get_official_documentation_url

def migration_versions_between(from_version: str, to_version: str) -> list[str]:
    try:
        start = int(float(from_version)) + 1
        end = int(float(to_version))
    except ValueError:
        return [to_version] if to_version else []
    return [f"{version}.0" for version in range(start, end + 1)]


def default_migration_version(version: str) -> str:
    if version in ODOO_VERSIONS:
        return f"{version}.1.0.0"
    return version


def migration_operation_list(title: str, items: list[dict[str, str]], formatter) -> str:
    if not items:
        return f"# {title}: none declared\n"
    lines = [f"# {title}"]
    for item in items:
        lines.extend(formatter(item))
    return "\n".join(lines) + "\n"


def create_upgrade_script(
    module_name: str,
    from_version: str,
    to_version: str,
    migration_version: str = "",
    rename_models: list[dict[str, str]] | None = None,
    rename_fields: list[dict[str, str]] | None = None,
    rename_xmlids: list[dict[str, str]] | None = None,
    data_migrations: list[str] | None = None,
    oca_style: bool = True,
) -> str:
    rename_models = rename_models or []
    rename_fields = rename_fields or []
    rename_xmlids = rename_xmlids or []
    data_migrations = normalized_string_list(data_migrations)
    target_version = migration_version or default_migration_version(to_version or current_version["value"])
    migration_dir = f"migrations/{target_version}"
    intermediate_versions = migration_versions_between(from_version, to_version)
    oca_note = "OCA-style migration layout" if oca_style else "Generic Odoo migration layout"

    def model_formatter(item: dict[str, str]) -> list[str]:
        old = item.get("old", "old.model")
        new = item.get("new", "new.model")
        return [
            f"# TODO: rename model `{old}` -> `{new}`.",
            f"# util.rename_model(cr, '{old}', '{new}', rename_table=True)",
            f"# Caveat: m2m table rename defaults differ before/after saas~18.1; pass ignored_m2ms explicitly when needed.",
        ]

    def field_formatter(item: dict[str, str]) -> list[str]:
        model = item.get("model", "your.model")
        old = item.get("old", "old_field")
        new = item.get("new", "new_field")
        return [
            f"# TODO: rename field `{model}.{old}` -> `{model}.{new}`.",
            f"# util.rename_field(cr, '{model}', '{old}', '{new}', update_references=True)",
        ]

    def xmlid_formatter(item: dict[str, str]) -> list[str]:
        old = item.get("old", f"{module_name}.old_xmlid")
        new = item.get("new", f"{module_name}.new_xmlid")
        return [
            f"# TODO: rename XML ID `{old}` -> `{new}`.",
            f"# util.rename_xmlid(cr, '{old}', '{new}', on_collision='fail')",
        ]

    pre_ops = "".join([
        migration_operation_list("Model renames", rename_models, model_formatter),
        migration_operation_list("Field renames", rename_fields, field_formatter),
        migration_operation_list("XML ID renames", rename_xmlids, xmlid_formatter),
    ])
    data_ops = "\n".join(f"    # TODO: {item}" for item in data_migrations) or "    # TODO: Add data migrations that require the upgraded registry."
    pre_helper_notes = '''    # Common pre-migration helpers from odoo.upgrade.util:
    # - util.column_exists(cr, "your_table", "old_column")
    # - util.table_exists(cr, "your_table")
    # - util.remove_field(cr, "your.model", "old_field", drop_column=False)
    # - util.copy_column(cr, "your_table", "old_column", "old_column_upg_copy")
    # - util.alter_column_type(cr, "your_table", "amount", "numeric", using="{0}::numeric")
    # - util.remove_model(cr, "old.model", drop_table=True)
    # - util.merge_model(cr, "old.model", "new.model", fields_mapping={"old_field": "new_field"})
'''

    pre_script = f'''# Copyright <year> <author>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.en.html).

from odoo.upgrade import util


def migrate(cr, version):
    if not version:
        return

{''.join('    ' + line + chr(10) for line in pre_ops.splitlines())}
{pre_helper_notes}'''

    post_script = f'''# Copyright <year> <author>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.en.html).

from odoo.upgrade import util


def migrate(cr, version):
    if not version:
        return
    env = util.env(cr)

{data_ops}
    # Recompute stored fields in batches after data changes.
    # util.recompute_fields(cr, "your.model", ["field_name"], query="SELECT id FROM your_table")

    # Iterate safely over large recordsets when ORM writes are required.
    # Model = env["your.model"]
    # ids = Model.search([]).ids
    # for record in util.iter_browse(Model, ids, chunk_size=1000):
    #     record.field_name = "value"
    # util.flush(Model)
    # util.invalidate(Model)
'''

    end_script = f'''# Copyright <year> <author>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.en.html).

from odoo.upgrade import util


def migrate(cr, version):
    if not version:
        return
    env = util.env(cr)

    # TODO: Add final checks that require all modules to be loaded.
    # - Validate migrated records.
    # - Remove temporary bridge data.
    # - Backfill values depending on other upgraded modules.
    # - Refresh noupdate XML records only when appropriate.
    # util.update_record_from_xml(cr, "{module_name}.record_xmlid", fields={{"name"}})
'''

    upgrade_util_helpers = f"""
## Verified `odoo.upgrade.util` Helper Map

These helpers come from `odoo.upgrade.util` and are intended as examples to adapt, not blind substitutions. Keep scripts idempotent and verify each old/new name against the database you are upgrading.

### Pre-Migration Schema Helpers

```python
from odoo.upgrade import util

# Models: update ir.model, references, xmlids, and optionally database tables.
util.rename_model(cr, "old.model", "new.model", rename_table=True)
util.remove_model(cr, "old.model", drop_table=True)
util.merge_model(cr, "old.model", "new.model", fields_mapping={{"old_field": "new_field"}})

# Fields: update metadata, filters, domains, exports, server actions, attachments, and inherited models.
util.rename_field(cr, "your.model", "old_field", "new_field", update_references=True)
util.remove_field(cr, "your.model", "old_field", drop_column=False)
util.move_field_to_module(cr, "your.model", "field_name", "old_module", "{module_name}")

# Raw SQL safety helpers for tables and columns.
if util.table_exists(cr, "your_table") and util.column_exists(cr, "your_table", "old_column"):
    util.copy_column(cr, "your_table", "old_column", "old_column_upg_copy")
    util.alter_column_type(cr, "your_table", "old_column", "text")
```

### XML ID And Record Helpers

```python
from odoo.upgrade import util

util.rename_xmlid(cr, "{module_name}.old_xmlid", "{module_name}.new_xmlid", on_collision="fail")
util.force_noupdate(cr, "{module_name}.record_xmlid", noupdate=True)
util.if_unchanged(cr, "{module_name}.record_xmlid", util.update_record_from_xml)
util.delete_unused(cr, "{module_name}.old_record_xmlid", deactivate=True)
```

### Post/End ORM Helpers

```python
from odoo.upgrade import util

env = util.env(cr)
util.recompute_fields(cr, "your.model", ["stored_field"], query="SELECT id FROM your_table")

Model = env["your.model"]
for record in util.iter_browse(Model, Model.search([]).ids, chunk_size=1000):
    record.active = True
util.flush(Model)
util.invalidate(Model)
```

### Module-Level Helpers

Module operations usually belong in a `base` migration script or an Odoo 16+ `--pre-upgrade-scripts` path before `base` loads, not in an arbitrary addon migration file.

```python
from odoo.upgrade import util

util.rename_module(cr, "old_module", "{module_name}")
util.merge_module(cr, "old_module", "{module_name}", update_dependers=True)
util.remove_module(cr, "old_module")
util.module_deps_diff(cr, "{module_name}", plus=("mail",), minus=("old_dependency",))
util.force_install_module(cr, "new_dependency", if_installed=["{module_name}"])
```
"""

    intermediate_output = ", ".join(intermediate_versions) if intermediate_versions else "No intermediate versions detected."
    version_dir_note = "" if migration_version else f"- This helper derived `{target_version}` from target Odoo version `{to_version or current_version['value']}`. Pass `migration_version` when the target manifest version differs."
    oca_20_note = """
- OCA 20.0 migration protocol says to bump the module to `20.0.1.0.0` and remove previous `migrations/` folders unless the migration issue explicitly justifies new scripts.
- Treat generated 20.0 scripts as a deliberate deviation from the short OCA 20.0 checklist; raise that on the migration issue before shipping them.
""" if oca_style and to_version == "20.0" else ""
    oca_checks = f"""
- Keep migration-only compatibility changes separate from behavior changes.
- Do not change original authors or copyright years while migrating.
- Apply every intermediate version checklist when jumping multiple major versions.
- Prefer the migration conventions already used by the repository.
- Use full module-version directories such as `migrations/{target_version}/`; some projects use `upgrades/` instead, so follow the target repository convention.
{version_dir_note}
{oca_20_note}
- Do not run module update/test commands against a database until the local command is confirmed.
""" if oca_style else "- Follow the migration conventions used by this project."

    return f"""# Upgrade Script Scaffold: `{module_name}` {from_version} -> {to_version}

Style: {oca_note}
Target migration directory: `{migration_dir}/`
Intermediate version checkpoints: {intermediate_output}

## File: `{migration_dir}/pre-migration.py`

Use this for schema-level compatibility work before the registry for the new module version is fully loaded.

```python
{pre_script}
```

## File: `{migration_dir}/post-migration.py`

Use this for data migrations after the upgraded registry is available.

```python
{post_script}
```

## File: `{migration_dir}/end-migration.py`

Use this for final checks after all modules in the upgrade set are loaded.

```python
{end_script}
```

## Data Migration Checklist

- Confirm renamed models, fields, and XML IDs against the old and new code.
- Check security CSVs, record rules, actions, views, reports, mail templates, and automations for old model/field/XML ID references.
- Add idempotency: migration scripts should tolerate being retried after partial failure.
- Backfill required fields before constraints make records invalid.
- Recompute stored computed fields only after source data is migrated.
- Add a test or manual verification query for each important migration rule.

{upgrade_util_helpers}

## OCA-Style Notes

{oca_checks}

## References

- Upgrade scripts: {get_official_documentation_url(to_version if to_version in ODOO_VERSIONS else current_version['value'], 'reference/upgrades/upgrade_scripts#writing-upgrade-scripts')}
- Upgrade utils: {get_official_documentation_url(to_version if to_version in ODOO_VERSIONS else current_version['value'], 'reference/upgrades/upgrade_utils')}
"""
