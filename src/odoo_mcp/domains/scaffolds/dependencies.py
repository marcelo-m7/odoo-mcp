from __future__ import annotations

from ...runtime.state import ODOO_VERSIONS, current_version
from ...utils.formatting import normalized_string_list

MODULE_DEPENDENCIES: dict[str, list[str]] = {
    "base": [],
    "web": ["base"],
    "mail": ["base"],
    "resource": ["base"],
    "digest": ["mail"],
    "sms": ["mail"],
    "base_automation": ["base", "digest", "resource", "mail", "sms"],
    "contacts": ["base"],
    "product": ["base", "mail", "uom"],
    "uom": ["base"],
    "account": ["base", "mail", "uom", "product"],
    "payment": ["account", "website"],
    "sale": ["base", "mail", "account", "product"],
    "sale_management": ["sale"],
    "purchase": ["base", "mail", "account", "product"],
    "stock": ["product", "mail"],
    "mrp": ["stock"],
    "project": ["mail", "web"],
    "hr": ["resource", "mail"],
    "crm": ["mail", "contacts"],
    "portal": ["web", "mail"],
    "website": ["web", "portal"],
    "website_sale": ["website", "sale_management", "payment"],
    "analytic": ["base"],
}


FEATURE_MODULE_HINTS: list[tuple[set[str], str]] = [
    ({"automation", "automated", "base.automation", "server action"}, "base_automation"),
    ({"mail", "message", "chatter", "activity", "followers", "notification"}, "mail"),
    ({"portal", "customer portal"}, "portal"),
    ({"website", "webpage", "web controller"}, "website"),
    ({"frontend", "owl", "asset", "javascript", "webclient"}, "web"),
    ({"sale", "sales", "quotation", "sale.order"}, "sale_management"),
    ({"purchase", "vendor", "purchase.order"}, "purchase"),
    ({"stock", "inventory", "warehouse", "picking", "stock.move"}, "stock"),
    ({"invoice", "account", "accounting", "account.move", "tax"}, "account"),
    ({"payment", "transaction", "provider"}, "payment"),
    ({"project", "task", "project.task"}, "project"),
    ({"employee", "hr", "attendance", "leave"}, "hr"),
    ({"crm", "lead", "opportunity"}, "crm"),
    ({"product", "product.template", "product.product"}, "product"),
    ({"manufacturing", "mrp", "bom"}, "mrp"),
    ({"analytic", "budget"}, "analytic"),
]


def collect_module_dependencies(module: str, seen: set[str], ordered: list[str]) -> None:
    if module in seen:
        return
    seen.add(module)
    for dependency in MODULE_DEPENDENCIES.get(module, []):
        collect_module_dependencies(dependency, seen, ordered)
    ordered.append(module)


def layout_module_dependencies(
    module_name: str,
    features: list[str] | None = None,
    models: list[str] | None = None,
    integrate_with: list[str] | None = None,
    explicit_dependencies: list[str] | None = None,
    include_transitive: bool = False,
    version: str = "",
) -> str:
    dependency_version = version if version in ODOO_VERSIONS else current_version["value"]
    features = normalized_string_list(features)
    models = normalized_string_list(models)
    integrate_with = normalized_string_list(integrate_with)
    explicit_dependencies = normalized_string_list(explicit_dependencies)
    requested_modules = {dep.strip() for dep in explicit_dependencies if dep.strip()}
    requested_modules.add("base")

    searchable_inputs = " ".join([module_name, *features, *models, *integrate_with]).lower()
    for keywords, module in FEATURE_MODULE_HINTS:
        if any(keyword in searchable_inputs for keyword in keywords):
            requested_modules.add(module)
    for integration in integrate_with:
        integration = integration.strip()
        if integration:
            requested_modules.add(integration)

    ordered_with_transitive: list[str] = []
    seen: set[str] = set()
    for module in sorted(requested_modules):
        collect_module_dependencies(module, seen, ordered_with_transitive)

    if include_transitive:
        manifest_depends = ordered_with_transitive
    else:
        # Keep direct module intent in the manifest; Odoo installs transitive dependencies automatically.
        manifest_depends = [module for module in ordered_with_transitive if module in requested_modules]

    unknown_modules = sorted(module for module in requested_modules if module not in MODULE_DEPENDENCIES)
    manifest_list = ", ".join(f"'{module}'" for module in manifest_depends)
    transitive_list = ", ".join(f"'{module}'" for module in ordered_with_transitive)
    unknown_output = "\n".join(f"- `{module}` is not in the built-in dependency map; verify its manifest manually." for module in unknown_modules) or "- No unknown modules detected."

    return f"""# Dependency Layout for `{module_name}` (Odoo {dependency_version})

## Recommended Manifest Dependencies

```python
'depends': [{manifest_list}],
```

## Full Installation Order

```python
[{transitive_list}]
```

## Why These Dependencies

""" + "\n".join(
        f"- `{module}`: requested directly or inferred from feature/model/integration inputs."
        for module in manifest_depends
    ) + f"""

## Unknowns To Verify

{unknown_output}

## Manifest Data Order Reminder

Use dependency order for modules, then data order inside your module:

```python
'data': [
    'security/groups.xml',
    'security/ir.model.access.csv',
    'security/record_rules.xml',
    'data/sequences.xml',
    'data/automations.xml',
    'views/model_views.xml',
    'views/menus.xml',
],
```

## Guardrails

- Add a dependency when you reference another module's model, field, view, group, menu, report, asset, or XML ID.
- Do not depend on a module just because it is installed in your database.
- Prefer the narrowest module that owns the XML IDs you use.
- For automated actions generated by `create_base_automation`, add `base_automation` explicitly.
- For chatter, activities, followers, or message posting, add `mail` explicitly.
"""
