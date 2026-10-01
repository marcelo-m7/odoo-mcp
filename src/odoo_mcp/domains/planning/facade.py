from __future__ import annotations

from ...runtime.paths import RULES_BASE_PATH
from ...runtime.state import ODOO_VERSIONS, current_version
from ..docs.facade import get_official_documentation_url

def get_skill_informed_guidance() -> str:
    return """## Odoo Operating Discipline

- Detect the target Odoo version before version-sensitive work.
- If `ODOO_SOURCE`, `ODOO_BASE_COMMAND`, or `ODOO_TOOL_README` are configured, inspect local source/tooling context before guessing commands or framework behavior.
- Inspect existing manifests, models, views, security, controllers, assets, tests, and docs before proposing changes.
- Treat models, views, controllers, workflows, and access behavior as security-sensitive; check ACLs, record rules, groups, `sudo()`, and multi-company boundaries together.
- Prefer small idiomatic changes that follow existing addon structure.
- Verify behavior at the Odoo seam: ORM, form helper, access test, controller test, report rendering, or mocked integration.
- Ask before running commands that touch a database or local service.
"""


def get_development_rules(rule_name: str) -> str:
    valid_rules = {
        "clean-code": "clean-code.mdc",
        "odoo-development": "odoo-development.mdc",
        "all": None,
    }

    if rule_name not in valid_rules:
        return f"Unknown rule set. Available: {', '.join(valid_rules.keys())}"

    if rule_name == "all":
        content = "# Complete Development Guidelines\n\n"
        for rule_file in RULES_BASE_PATH.glob("*.mdc"):
            try:
                rule_content = rule_file.read_text(encoding="utf-8")
                content += f"\n\n---\n\n{rule_content}\n\n"
            except Exception:
                continue
        return content

    rule_file = RULES_BASE_PATH / valid_rules[rule_name]
    if not rule_file.exists():
        return f"Rule file not found: {rule_name}"

    try:
        return rule_file.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading rules: {str(e)}"

def get_development_guidelines(context: str = "general") -> str:
    contexts = {
        "general": ["clean-code", "odoo-development"],
        "models": ["odoo-development"],
        "views": ["odoo-development"],
        "security": ["odoo-development"],
        "all": ["clean-code", "odoo-development"]
    }

    if context not in contexts:
        context = "general"

    guidelines = f"# Development Guidelines for {context.title()} Context\n\n"
    guidelines += f"Current Odoo Version: {current_version['value']}\n\n"
    guidelines += get_skill_informed_guidance() + "\n"
    guidelines += "## Local Odoo Context\n\n"
    guidelines += "Use `get_odoo_local_context()` or `odoo://local/context` to inspect `ODOO_SOURCE`, `ODOO_BASE_COMMAND`, and `ODOO_TOOL_README` before proposing local Odoo commands.\n\n"

    rule_files = contexts[context]

    for rule_name in rule_files:
        rule_file = RULES_BASE_PATH / f"{rule_name}.mdc"
        if rule_file.exists():
            try:
                content = rule_file.read_text(encoding="utf-8")
                lines = content.split('\n')
                clean_content = []
                in_frontmatter = False
                frontmatter_count = 0

                for line in lines:
                    if line.strip() == '---':
                        frontmatter_count += 1
                        in_frontmatter = not in_frontmatter
                        continue
                    if not in_frontmatter and frontmatter_count >= 2:
                        clean_content.append(line)

                guidelines += '\n'.join(clean_content) + "\n\n---\n\n"
            except Exception:
                continue

    guidelines += "\n## Quick Reference Links\n\n"
    guidelines += f"- Full rules: odoo://rules/all\n"
    guidelines += f"- Clean code: odoo://rules/clean-code\n"
    guidelines += f"- Odoo conventions: odoo://rules/odoo-development\n"
    guidelines += f"- Official developer reference: {get_official_documentation_url(current_version['value'])}\n"
    guidelines += f"- ORM API: {get_official_documentation_url(current_version['value'], 'reference/backend/orm')}\n"
    guidelines += f"- Security: {get_official_documentation_url(current_version['value'], 'reference/backend/security')}\n"
    guidelines += f"- Testing: {get_official_documentation_url(current_version['value'], 'reference/backend/testing')}\n"

    return guidelines

def plan_odoo_feature(feature_description: str, module_name: str = "", version: str = "") -> str:
    """Create a skill-informed implementation plan for an Odoo feature."""
    plan_version = version if version in ODOO_VERSIONS else current_version["value"]
    words = [
        word
        for word in "".join(char.lower() if char.isalnum() else " " for char in feature_description).split()
        if len(word) > 2
    ]
    if not module_name:
        module_name = "_".join(words[:3]) if words else "custom_feature"
    else:
        module_name = "_".join(
            word
            for word in "".join(char.lower() if char.isalnum() else " " for char in module_name).split()
            if word
        ) or "custom_feature"

    model_stem = module_name.replace("_management", "").replace("_", ".")
    primary_model = f"{model_stem}.record" if "." not in model_stem else f"{model_stem}.record"
    collection_view = "list" if plan_version in {"18.0", "19.0"} else "tree"
    safe_description = feature_description[:80].replace("'", "\\'")

    doc_links = {
        "Module manifests": get_official_documentation_url(plan_version, "reference/backend/module"),
        "ORM fields and models": get_official_documentation_url(plan_version, "reference/backend/orm#fields"),
        "Actions and menus": get_official_documentation_url(plan_version, "reference/backend/actions#window-actions-ir-actions-act-window"),
        "View architectures": get_official_documentation_url(plan_version, "reference/user_interface/view_architectures"),
        "Access rights": get_official_documentation_url(plan_version, "reference/backend/security#access-rights"),
        "Record rules": get_official_documentation_url(plan_version, "reference/backend/security#record-rules"),
        "Testing": get_official_documentation_url(plan_version, "reference/backend/testing#testing-python-code"),
    }

    return f"""# Odoo Feature Plan: {feature_description}

Target version: Odoo {plan_version}
Suggested module: `{module_name}`
Suggested primary model: `{primary_model}`

## Implementation Shape

1. Confirm scope and version-sensitive behavior.
2. Create or update module manifest and dependencies.
3. Add the primary model with only the fields needed for the first workflow.
4. Add ACLs before loading views.
5. Add `{collection_view}`, form, and search views.
6. Add an `ir.actions.act_window` and menu only under a real parent menu XML ID.
7. Add tests at the Odoo behavior seam before expanding the feature.

## Model Sketch

Start with a small model and add business fields only when the workflow needs them:

```python
from odoo import fields, models


class {''.join(part.title() for part in primary_model.split('.'))}(models.Model):
    _name = '{primary_model}'
    _description = '{safe_description}'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
```

## Security Pass

- Add `security/ir.model.access.csv` for every new model.
- Decide whether normal internal users need read-only, create/write, or manager-only access.
- Add record rules when users must only see own, company, portal, or team records.
- Check `company_id`, default company behavior, domains, and cross-company reads/writes for business data.
- Do not use `sudo()` to hide missing access design.

## View And Action Pass

- Use `{collection_view}` collection views for Odoo {plan_version}.
- Keep form views minimal first: required fields, status fields, and primary relations.
- Keep search views focused on fields users actually filter by.
- Avoid placeholder menu parents. Pass a real parent XML ID to `create_odoo_view(..., parent_menu="module.menu_parent")` or add the menu later.

## Test Pass

- Add a `TransactionCase` for core ORM behavior.
- Add a Form helper test if the feature depends on form defaults/onchanges.
- Add an access test for intended groups and forbidden operations.
- Add an `HttpCase` only if the feature exposes controllers, portal routes, reports, or frontend flows.

## Suggested Tool Calls

```text
set_odoo_version("{plan_version}")
create_odoo_module("{module_name}", "{module_name.replace('_', ' ').title()}", "{feature_description}")
create_odoo_model("{primary_model}", "{safe_description}", fields=[{{"name": "active", "type": "Boolean"}}])
create_security_rules("{primary_model}", "{module_name}")
create_odoo_view("{primary_model}", "{collection_view}", ["name", "active"])
create_odoo_view("{primary_model}", "form", ["name", "active"])
```

## Official References

""" + "\n".join(f"- {title}: {url}" for title, url in doc_links.items()) + "\n"

def develop_odoo_feature(feature_description: str) -> str:
    return f"""I need to develop a new feature for Odoo {current_version['value']}:

Feature: {feature_description}

Official reference: {get_official_documentation_url(current_version['value'])}

Please help me following Odoo development guidelines:

1. Design the data model (models and fields needed)
   - Follow naming conventions (models use dots, fields use underscores)
   - Use proper field types and parameters

2. Create the necessary views (form, tree, search)
   - Follow view naming conventions
   - Use proper XML structure

3. Set up security rules
   - Define access rights in CSV
   - Add record rules if needed

4. Implement any business logic needed
   - Use proper decorators (@api.depends, @api.constrains, etc.)
   - Follow method naming conventions

5. Follow Odoo best practices and coding guidelines
   - Review: get_development_guidelines("general")
   - Check: odoo://rules/odoo-development

What models, views, and logic do I need to implement this feature?
"""


def debug_odoo_error(error_message: str, context: str = "") -> str:
    return f"""I'm encountering an error in Odoo {current_version['value']}:

Error: {error_message}

Context: {context}

Official reference: {get_official_documentation_url(current_version['value'])}

Please help me following Odoo debugging best practices:

1. Identify the root cause of this error
   - Check common Odoo pitfalls (see guidelines)
   - Verify naming conventions
   - Check for SQL constraints violations

2. Suggest solutions based on Odoo best practices
   - Use proper ORM methods
   - Follow Odoo patterns
   - Avoid common mistakes

3. Provide code examples if needed
   - Show correct implementation
   - Reference Odoo documentation

4. Explain how to prevent this error in the future
   - Follow guidelines: get_development_guidelines()
   - Review: odoo://rules/odoo-development

What's causing this error and how can I fix it?
"""


def upgrade_odoo_module(module_name: str, from_version: str, to_version: str) -> str:
    return f"""I need to upgrade the Odoo module '{module_name}' from version {from_version} to {to_version}.

Official upgrade reference: {get_official_documentation_url(to_version, 'reference/upgrades')}

Please help me:
1. Identify breaking changes between versions
2. List deprecated APIs that need updating
3. Suggest migration steps
4. Provide code examples for common migration patterns
5. Highlight any new features I should consider using

What changes do I need to make to upgrade this module?
"""


def review_odoo_code(code: str) -> str:
    return f"""Please review this Odoo code for version {current_version['value']} against Odoo development guidelines:

Official reference: {get_official_documentation_url(current_version['value'])}

```python
{code}
```

Check for compliance with Odoo standards:

1. **Naming Conventions**
   - Model names use dots (e.g., sale.order)
   - Field names: _id for Many2one, _ids for Many2many/One2many
   - Method names: _compute_, _onchange_, _check_ prefixes

2. **API Decorators**
   - Proper use of @api.depends, @api.constrains, @api.onchange
   - Correct decorator order

3. **ORM Best Practices**
   - Avoid SQL unless necessary
   - Use mapped(), filtered(), sorted()
   - Batch operations

4. **Performance Issues**
   - Check for N+1 queries
   - Inefficient loops
   - Missing indices

5. **Security Concerns**
   - SQL injection risks
   - Proper access control
   - Input validation

6. **Code Quality**
   - DRY principle
   - Single responsibility
   - Clear naming

Reference guidelines: odoo://rules/odoo-development

Provide specific suggestions for improvement.
"""
