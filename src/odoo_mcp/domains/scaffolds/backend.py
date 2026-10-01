from __future__ import annotations

from typing import Any

from ...runtime.state import current_version
from ...utils.formatting import normalized_string_list, python_string, xml_attr, xml_text
from ..docs.facade import get_official_documentation_url


def collection_view_type(version: str) -> str:
    return "tree" if version == "17.0" else "list"


def access_file(version: str) -> str:
    return "security/ir.access.csv" if version == "20.0" else "security/ir.model.access.csv"


def access_file_name(version: str) -> str:
    return access_file(version).split("/", 1)[1]


def create_odoo_module(
    module_name: str,
    display_name: str,
    description: str,
    author: str = "Your Company",
    category: str = "Uncategorized",
    depends: list[str] | None = None,
) -> str:
    version = current_version["value"]
    security_file = access_file(version)
    security_file_name = access_file_name(version)
    if version == "20.0":
        access_header = "id,name,model_id,group_id/id,operation,domain"
        access_example = f"access_{module_name}_user,{module_name} user,your.model,base.group_user,crud,"
        access_note = "\nOdoo 20 access rows use `ir.access` operations (`c`, `r`, `u`, `d`) and optional access domains. Replace `your.model` with the model technical name.\n"
    else:
        access_header = "id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink"
        access_example = f"access_{module_name}_user,{module_name}.user,model_{module_name}_model,base.group_user,1,1,1,1"
        access_note = ""
    depends = normalized_string_list(depends, ["base"])
    if not depends:
        depends = ["base"]

    manifest_content = f'''{{
    'name': {python_string(display_name)},
    'version': '{version}.1.0.0',
    'category': {python_string(category)},
    'summary': {python_string(description)},
    'description': {python_string(description)},
    'author': {python_string(author)},
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',
    'depends': {depends!r},
    'data': [
        {python_string(security_file)},
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}}
'''

    init_content = '''from . import cli
from . import models
from . import wizards
'''

    doc_reference = get_official_documentation_url(version, "reference/backend/module")
    rules_reference = "odoo://rules/odoo-development"

    structure = f"""# Module Structure for {module_name} (Odoo {version})

## Directory Structure

{module_name}/
├── __init__.py
├── __manifest__.py
├── models/
│   └── __init__.py
├── wizards/
│   └── __init__.py
├── cli/
│   └── __init__.py
├── views/
├── security/
│   └── {security_file_name}
├── data/
└── static/
    └── description/
        └── icon.png

## File Contents

### __manifest__.py
```python
{manifest_content}
```

### __init__.py
```python
{init_content}
```

### models/__init__.py
```python
# Import your models here
```

### wizards/__init__.py
```python
# Import your transient models here
```

### cli/__init__.py
```python
# Import your CLI helpers here, if this module exposes any
```

### {security_file}
```csv
{access_header}
{access_example}
```
{access_note}
## Naming Convention Rules ⚠️
- **Module name**: Use lowercase_with_underscores (e.g., `sale_extended`)
- **Technical name**: Same as directory name
- **Display name**: Human-readable (e.g., "Sales Extended")
- **Never use hyphens** in module names

## Next Steps
1. Create the directory structure above
2. Add models: `create_odoo_model()`
3. Add views: `create_odoo_view()`
4. Configure security: `create_security_rules()`
5. Review guidelines: `get_development_guidelines("general")`

## References
- Documentation: {doc_reference}
- Development Rules: {rules_reference}
- Naming Conventions: See "Module Structure" in rules
"""

    return structure


def create_odoo_model(
    model_name: str,
    model_description: str,
    fields: list[dict[str, Any]],
    inherit: str = ""
) -> str:
    class_name = "".join(word.capitalize() for word in model_name.split("."))

    field_definitions = []
    for field in fields:
        field_name = field.get("name", "field")
        field_type = field.get("type", "Char")
        field_string = field.get("string", field_name.replace("_", " ").title())
        required = field.get("required", False)

        if field_type == "Many2one":
            comodel = field.get("comodel_name", "res.partner")
            field_def = f'    {field_name} = fields.Many2one({python_string(comodel)}, string={python_string(field_string)}, required={required})'
        elif field_type == "One2many":
            comodel = field.get("comodel_name")
            inverse = field.get("inverse_name")
            field_def = f'    {field_name} = fields.One2many({python_string(comodel)}, {python_string(inverse)}, string={python_string(field_string)})'
        elif field_type == "Many2many":
            comodel = field.get("comodel_name")
            field_def = f'    {field_name} = fields.Many2many({python_string(comodel)}, string={python_string(field_string)})'
        elif field_type == "Selection":
            selection = field.get("selection", "[('draft', 'Draft'), ('done', 'Done')]")
            field_def = f'    {field_name} = fields.Selection({selection}, string={python_string(field_string)}, required={required})'
        else:
            field_def = f'    {field_name} = fields.{field_type}(string={python_string(field_string)}, required={required})'

        field_definitions.append(field_def)

    fields_code = "\n".join(field_definitions)
    version = current_version["value"]

    if inherit:
        model_code = f'''from odoo import models, fields, api


class {class_name}(models.Model):
    _inherit = {python_string(inherit)}

{fields_code}
'''
    else:
        model_code = f'''from odoo import models, fields, api


class {class_name}(models.Model):
    _name = {python_string(model_name)}
    _description = {python_string(model_description)}

    name = fields.Char(string='Name', required=True)
{fields_code}
'''

    doc_reference = get_official_documentation_url(version, "reference/backend/orm")
    rules_reference = "odoo://rules/odoo-development"

    return f"""# Model Definition for {model_name} (Odoo {version})

**File**: models/{model_name.replace('.', '_')}.py

```python
{model_code}
```

## Naming Convention Rules ⚠️
- **Model name**: Use dots (e.g., `sale.order.line`, not `sale_order_line`)
- **Class name**: CamelCase (e.g., `SaleOrderLine`)
- **Field naming**:
  - Boolean: Start with `is_`, `has_`, `can_`
  - Many2one: End with `_id`
  - One2many/Many2many: End with `_ids`
- **Method naming**: Use `_compute_`, `_onchange_`, `_check_` prefixes

## Next Steps
1. Import in models/__init__.py: `from . import {model_name.replace('.', '_')}`
2. Add security: `create_security_rules("{model_name}", "module_name")`
3. Create views: `create_odoo_view("{model_name}", "form", [fields])`
4. Review guidelines: `get_development_guidelines("models")`

## References
- ORM Documentation: {doc_reference}
- Development Rules: {rules_reference}
- See "Python Coding Standards" section in rules
"""


def create_odoo_view(
    model_name: str,
    view_type: str,
    fields_to_display: list[str],
    view_name: str = "",
    parent_menu: str = ""
) -> str:
    version = current_version["value"]
    requested_view_type = view_type.lower().strip()
    collection_type = collection_view_type(version)
    normalized_view_type = collection_type if requested_view_type in {"tree", "list"} else requested_view_type

    if normalized_view_type not in {"list", "tree", "form", "search", "kanban"}:
        return f"Unsupported view type: {view_type}. Supported types: list/tree, form, search, kanban"

    if not view_name:
        view_name = f"{model_name.replace('.', '_')}_{normalized_view_type}_view"

    model_underscore = model_name.replace(".", "_")
    display_name = model_name.split(".")[-1].replace("_", " ").title()
    model_name_xml = xml_text(model_name)
    view_name_attr = xml_attr(view_name)
    model_underscore_attr = xml_attr(model_underscore)
    display_name_xml = xml_text(display_name)
    display_name_attr = xml_attr(display_name)

    if normalized_view_type in {"tree", "list"}:
        fields_xml = "\n            ".join([f'<field name="{xml_attr(field)}"/>' for field in fields_to_display])
        view_xml = f'''<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="{view_name_attr}" model="ir.ui.view">
        <field name="name">{model_name_xml}.{normalized_view_type}</field>
        <field name="model">{model_name_xml}</field>
        <field name="arch" type="xml">
            <{normalized_view_type}>
                {fields_xml}
            </{normalized_view_type}>
        </field>
    </record>
</odoo>'''

    elif normalized_view_type == "form":
        fields_xml = "\n                    ".join([f'<field name="{xml_attr(field)}"/>' for field in fields_to_display])
        view_xml = f'''<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="{view_name_attr}" model="ir.ui.view">
        <field name="name">{model_name_xml}.form</field>
        <field name="model">{model_name_xml}</field>
        <field name="arch" type="xml">
            <form>
                <sheet>
                    <group>
                        {fields_xml}
                    </group>
                </sheet>
            </form>
        </field>
    </record>
</odoo>'''

    elif normalized_view_type == "search":
        fields_xml = "\n                ".join([f'<field name="{xml_attr(field)}"/>' for field in fields_to_display])
        view_xml = f'''<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="{view_name_attr}" model="ir.ui.view">
        <field name="name">{model_name_xml}.search</field>
        <field name="model">{model_name_xml}</field>
        <field name="arch" type="xml">
            <search>
                {fields_xml}
            </search>
        </field>
    </record>
</odoo>'''

    else:
        kanban_fields = fields_to_display or ["name"]
        field_declarations = "\n                ".join([f'<field name="{xml_attr(field)}"/>' for field in kanban_fields])
        card_lines = "\n                                    ".join([f'<div><field name="{xml_attr(field)}"/></div>' for field in kanban_fields[:4]])
        view_xml = f'''<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="{view_name_attr}" model="ir.ui.view">
        <field name="name">{model_name_xml}.kanban</field>
        <field name="model">{model_name_xml}</field>
        <field name="arch" type="xml">
            <kanban>
                {field_declarations}
                <templates>
                    <t t-name="kanban-box">
                        <div class="oe_kanban_card">
                            <div class="oe_kanban_content">
                                {card_lines}
                            </div>
                        </div>
                    </t>
                </templates>
            </kanban>
        </field>
    </record>
</odoo>'''

    if parent_menu:
        menu_xml = f'''    <menuitem id="menu_{model_underscore_attr}"
              name="{display_name_attr}"
              action="action_{model_underscore_attr}"
              parent="{xml_attr(parent_menu)}"/>'''
    else:
        menu_xml = f'''    <!-- Add a menu only after choosing a real parent menu:
    <menuitem id="menu_{model_underscore_attr}"
              name="{display_name_attr}"
              action="action_{model_underscore_attr}"
              parent="your_module.menu_parent"/>
    -->'''

    action_xml = f'''    <record id="action_{model_underscore_attr}" model="ir.actions.act_window">
        <field name="name">{display_name_xml}</field>
        <field name="res_model">{model_name_xml}</field>
        <field name="view_mode">{collection_type},form</field>
    </record>

{menu_xml}'''

    doc_reference = get_official_documentation_url(version, "reference/user_interface/view_architectures")
    action_reference = get_official_documentation_url(version, "reference/backend/actions#window-actions-ir-actions-act-window")
    test_reference = get_official_documentation_url(version, "reference/backend/testing")
    rules_reference = "odoo://rules/odoo-development"
    security_guardrail = "Add `ir.access` rows and access domains separately." if version == "20.0" else "Add ACLs and record rules separately."
    alias_note = ""
    if requested_view_type in {"tree", "list"} and requested_view_type != normalized_view_type:
        alias_note = f"\nRequested `{requested_view_type}`; generated `{normalized_view_type}` because Odoo {version} uses `{normalized_view_type}` for collection views.\n"

    return f"""# {normalized_view_type.title()} View for {model_name} (Odoo {version})

**File**: views/{model_underscore}_views.xml
{alias_note}
```xml
{view_xml}
```

## Action and Menu

The action uses `{collection_type},form` for Odoo {version}. A menu item is only generated when `parent_menu` is provided; otherwise choose a real parent menu from your module or dependency.

```xml
<odoo>
{action_xml}
</odoo>
```

## Manifest Configuration

Add to __manifest__.py 'data' section after security files:
```python
'data': [
    {python_string(access_file(version))},
    'views/{model_underscore}_views.xml',
],
```

## Odoo View Guardrails
- **Collection views**: Odoo 17 uses `tree`; Odoo 18+ uses `list`.
- **Action view_mode**: Keep it aligned with the generated collection view type.
- **Menu parent**: Do not use placeholder parents like `base.menu_custom`; pass a real `parent_menu` XML ID or add the menu later.
- **Security**: Views do not grant access. {security_guardrail}
- **Tests**: For important workflows, add a Form helper test or access test covering the generated view's model.

## Next Steps
1. Add this file to your manifest's 'data' section after security files
2. Add or confirm ACLs with `create_security_rules("{model_name}", "module_name")`
3. Test the view in Odoo with a user matching the intended group
4. Review guidelines: `get_development_guidelines("views")`

## References
- View Architecture: {doc_reference}
- Window Actions: {action_reference}
- Testing: {test_reference}
- Development Rules: {rules_reference}
"""


def create_security_rules(
    model_name: str,
    module_name: str,
    groups: list[str] | None = None,
) -> str:
    groups = normalized_string_list(groups, ["user", "manager"])
    if not groups:
        groups = ["user", "manager"]
    for csv_value, csv_label in [(model_name, "model_name"), (module_name, "module_name"), *[(group, "group") for group in groups]]:
        if "," in csv_value or "\n" in csv_value or "\r" in csv_value:
            return f"Error: {csv_label} must not contain commas or newlines"

    model_underscore = model_name.replace(".", "_")
    version = current_version["value"]

    if version == "20.0":
        csv_lines = ["id,name,model_id,group_id/id,operation,domain"]
    else:
        csv_lines = ["id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink"]

    for group in groups:
        if version == "20.0":
            operation = "r" if group == "user" else "crud"
            group_ref = "base.group_system" if group == "manager" else f"base.group_{group}"
            line = f"access_{model_underscore}_{group},{model_name} {group},{model_name},{group_ref},{operation},"
        else:
            if group == "user":
                perms = "1,0,0,0"
            elif group == "manager":
                perms = "1,1,1,1"
            else:
                perms = "1,1,1,1"
            line = f"access_{model_underscore}_{group},{module_name}.{group},model_{model_underscore},base.group_{group},{perms}"
        csv_lines.append(line)

    csv_content = "\n".join(csv_lines)
    doc_reference = get_official_documentation_url(version, "reference/backend/security")
    rules_reference = "odoo://rules/odoo-development"
    security_file = access_file(version)

    if version == "20.0":
        return f"""# Security Rules for {model_name} (Odoo {version})

## Access Rights And Domains (CSV)

**File**: {security_file}

```csv
{csv_content}
```

## Odoo 20 Security Guidelines ⚠️
- **Access model**: Use `ir.access` rows with `operation` letters (`c`, `r`, `u`, `d`).
- **Record filtering**: Put row-level restrictions in the `domain` column of the relevant access row.
- **All users**: Use `base.group_everyone` for all users; avoid blank `group_id` unless you need a global restriction.
- **Migration note**: Do not copy older `ir.model.access`/`perm_*` or separate `ir.rule` examples into new Odoo 20 scaffolds.
- **Testing**: Test realistic users, groups, companies, and negative access cases.

## Manifest Configuration

Add to __manifest__.py 'data' section (order matters):
```python
'data': [
    {python_string(security_file)},
    'views/{model_underscore}_views.xml',
],
```

## Next Steps
1. Add security files to manifest in correct order
2. Add `domain` values where users should only access own, company, portal, or team records
3. Test with different user roles and companies
4. Review guidelines: `get_development_guidelines("security")`

## References
- Security Documentation: {doc_reference}
- Development Rules: {rules_reference}
- See Odoo 20 access/domain guidance before migrating older security snippets
"""

    return f"""# Security Rules for {model_name} (Odoo {version})

## Access Rights (CSV)

**File**: security/ir.model.access.csv

```csv
{csv_content}
```

## Record Rules (XML) - Optional

**File**: security/{module_name}_security.xml

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="{xml_attr(model_underscore)}_rule_own" model="ir.rule">
        <field name="name">{xml_text(model_name)}: See own records</field>
        <field name="model_id" ref="model_{xml_attr(model_underscore)}"/>
        <field name="domain_force">[('create_uid', '=', user.id)]</field>
        <field name="groups" eval="[(4, ref('base.group_user'))]"/>
    </record>
</odoo>
```

## Security Rules Guidelines ⚠️
- **Naming**: Use `access_{{model}}_{{group}}` format
- **Permissions**: Format is (read, write, create, unlink)
  - User group: Usually (1,0,0,0) - read-only
  - Manager group: Usually (1,1,1,1) - full access
- **Record Rules**: Use for row-level security
- **Testing**: Always test security with different user groups

## Manifest Configuration

Add to __manifest__.py 'data' section (order matters):
```python
'data': [
    'security/{module_name}_security.xml',  # Groups first (if any)
    'security/ir.model.access.csv',         # Access rights
    'views/{model_underscore}_views.xml',   # Views last
],
```

## Next Steps
1. Add security files to manifest in correct order
2. Test with different user roles
3. Review guidelines: `get_development_guidelines("security")`

## References
- Security Documentation: {doc_reference}
- Development Rules: {rules_reference}
- See "Security Standards" section in rules
"""
