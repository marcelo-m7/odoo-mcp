from __future__ import annotations

from ...runtime.state import ODOO_VERSIONS, current_version
from ...utils.formatting import js_string, normalized_string_list, python_string, xml_text
from ...utils.identifiers import camel_identifier, pascal_identifier, snake_identifier
from ..docs.facade import get_official_documentation_url

def identifier_words(value: str, fallback: str = "owl_component") -> list[str]:
    words: list[str] = []
    current = ""
    for char in value:
        if char.isalnum():
            current += char.lower()
        elif current:
            words.append(current)
            current = ""
    if current:
        words.append(current)
    return words or [fallback]


def snake_identifier(value: str, fallback: str = "owl_component") -> str:
    return "_".join(identifier_words(value, fallback))


def pascal_identifier(value: str, fallback: str = "OwlComponent") -> str:
    words = identifier_words(value, fallback.lower())
    return "".join(word[:1].upper() + word[1:] for word in words)


def camel_identifier(value: str, fallback: str = "service") -> str:
    pascal = pascal_identifier(value, fallback.title())
    return pascal[:1].lower() + pascal[1:]


def js_string_array(values: list[str]) -> str:
    return "[" + ", ".join(js_string(value) for value in values) + "]"


def owl_asset_paths(module_name: str, component_slug: str, category: str, include_scss: bool = True) -> list[str]:
    base_path = f"{module_name}/static/src/{category}/{component_slug}/{component_slug}"
    paths = [f"{base_path}.js", f"{base_path}.xml"]
    if include_scss:
        paths.append(f"{base_path}.scss")
    return paths


def owl_manifest_asset_snippet(bundle: str, paths: list[str]) -> str:
    lines = ["'assets': {", f"    {python_string(bundle)}: ["]
    lines.extend(f"        {python_string(path)}," for path in paths)
    lines.extend(["    ],", "},"])
    return "\n".join(lines)


def owl_props_object(props: list[str]) -> str:
    cleaned_props = [snake_identifier(prop, "prop") for prop in normalized_string_list(props)]
    if not cleaned_props:
        return "{}"
    body = ",\n        ".join(
        f"{prop}: {{ type: String, optional: true }}" for prop in cleaned_props
    )
    return "{\n        " + body + ",\n    }"


def owl_service_setup_lines(services: list[str]) -> str:
    cleaned_services = normalized_string_list(services)
    if not cleaned_services:
        return "        // Add component setup here."
    return "\n".join(
        f"        this.{camel_identifier(service)} = useService({js_string(service)});"
        for service in cleaned_services
    )


def owl_state_line(use_state: bool) -> str:
    return '        this.state = useState({ value: "" });' if use_state else ""


def owl_docs(version: str) -> dict[str, str]:
    return {
        "owl": get_official_documentation_url(version, "reference/frontend/owl_components"),
        "assets": get_official_documentation_url(version, "reference/frontend/assets"),
        "registries": get_official_documentation_url(version, "reference/frontend/registries"),
        "services": get_official_documentation_url(version, "reference/frontend/services"),
        "hooks": get_official_documentation_url(version, "reference/frontend/hooks"),
        "testing": get_official_documentation_url(version, "reference/frontend/unit_testing"),
    }


def plan_owl_feature(
    feature_description: str,
    module_name: str,
    integration_type: str = "component",
    target_bundle: str = "web.assets_backend",
    version: str = "",
) -> str:
    """Plan Odoo OWL frontend work with asset, registry, service, and test guardrails."""
    owl_version = version if version in ODOO_VERSIONS else current_version["value"]
    module_slug = snake_identifier(module_name, "custom_module")
    integration = integration_type.strip() or "component"
    docs = owl_docs(owl_version)

    registry_hint = {
        "component": "No registry is required unless another Odoo extension point loads this component.",
        "client_action": 'Use `registry.category("actions").add(tag, Component)` and an `ir.actions.client` record.',
        "field_widget": 'Use `registry.category("fields").add(widgetName, fieldDefinition)` and `standardFieldProps`.',
        "service": 'Use `registry.category("services").add(serviceName, serviceDefinition)` and declare dependencies explicitly.',
    }.get(integration, "Choose the narrowest registry category for the Odoo extension point you are targeting.")

    return f"""# OWL Feature Plan: {feature_description}

Target version: Odoo {owl_version}
Module: `{module_slug}`
Integration type: `{integration}`
Asset bundle: `{target_bundle}`

## Implementation Path

1. Confirm the Odoo version and existing frontend conventions in the target addon.
2. Put JS/XML/SCSS under `static/src/` using the addon structure already in the repo.
3. Register files in `__manifest__.py` under `{target_bundle}`.
4. Keep the component small: explicit props, local `useState` only for UI state, and services through `useService`.
5. Load templates via XML assets; use static `template = "{module_slug}.ComponentName"`.
6. Add the right registry entry only when integrating with an Odoo extension point.
7. Add a frontend test or tour around the user-visible behavior, not just component construction.

## Registry Guidance

{registry_hint}

## Guardrails

- Do not mutate `props`; send changes through callbacks, `record.update`, or services.
- Treat `t-raw`/unsafe HTML as a security boundary; prefer `t-esc`/`t-out`.
- Do not call RPC directly from random helpers when `orm`, `action`, `notification`, or `dialog` services fit.
- Check mobile behavior and `env.isSmall` before adding dense layouts.
- Restart/update assets and clear browser cache when testing templates or SCSS.

## References

- OWL components: {docs['owl']}
- Assets: {docs['assets']}
- Registries: {docs['registries']}
- Services: {docs['services']}
- Hooks: {docs['hooks']}
- Frontend testing: {docs['testing']}
"""


def create_owl_component(
    component_name: str,
    module_name: str,
    props: list[str] | None = None,
    services: list[str] | None = None,
    use_state: bool = False,
    target_bundle: str = "web.assets_backend",
    version: str = "",
) -> str:
    """Generate an Odoo OWL component scaffold with JS, XML, SCSS, and manifest assets."""
    props = normalized_string_list(props)
    services = normalized_string_list(services)
    owl_version = version if version in ODOO_VERSIONS else current_version["value"]
    module_slug = snake_identifier(module_name, "custom_module")
    component_slug = snake_identifier(component_name, "component")
    class_name = pascal_identifier(component_name, "OwlComponent")
    template_name = f"{module_slug}.{class_name}"
    paths = owl_asset_paths(module_slug, component_slug, "components")
    docs = owl_docs(owl_version)
    owl_imports = ["Component"] + (["useState"] if use_state else [])
    hook_import = '\nimport { useService } from "@web/core/utils/hooks";' if services else ""
    state_line = owl_state_line(use_state)
    setup_lines = "\n".join(line for line in [owl_service_setup_lines(services), state_line] if line)

    js = f'''import {{ {", ".join(owl_imports)} }} from "@odoo/owl";{hook_import}

export class {class_name} extends Component {{
    static template = "{template_name}";
    static props = {owl_props_object(props)};

    setup() {{
{setup_lines}
    }}
}}
'''

    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">
    <t t-name="{template_name}">
        <section class="o_{component_slug}">
            <h3>{class_name}</h3>
            <p t-if="props.title" t-esc="props.title"/>
            <p t-else="">Component ready.</p>
        </section>
    </t>
</templates>'''

    scss = f'''.o_{component_slug} {{
    display: flex;
    flex-direction: column;
    gap: .5rem;
}}'''

    return f"""# OWL Component Scaffold: `{class_name}` (Odoo {owl_version})

## Files

- `static/src/components/{component_slug}/{component_slug}.js`
- `static/src/components/{component_slug}/{component_slug}.xml`
- `static/src/components/{component_slug}/{component_slug}.scss`

## JS

```js
{js}
```

## XML Template

```xml
{xml}
```

## SCSS

```scss
{scss}
```

## Manifest Assets

```python
{owl_manifest_asset_snippet(target_bundle, paths)}
```

## Guardrails

- Template names should stay globally unique: `{template_name}`.
- Add services only through `useService` inside `setup()`.
- Keep data loading out of rendering getters; use lifecycle hooks/services for async work.

## References

- OWL components: {docs['owl']}
- Assets: {docs['assets']}
"""


def create_owl_client_action(
    action_name: str,
    module_name: str,
    action_tag: str = "",
    services: list[str] | None = None,
    target_bundle: str = "web.assets_backend",
    version: str = "",
) -> str:
    """Generate an Odoo OWL client action scaffold and matching ir.actions.client XML."""
    services = normalized_string_list(services)
    owl_version = version if version in ODOO_VERSIONS else current_version["value"]
    module_slug = snake_identifier(module_name, "custom_module")
    action_slug = snake_identifier(action_name, "client_action")
    class_name = pascal_identifier(action_name, "ClientAction")
    tag = action_tag.strip() or f"{module_slug}.{action_slug}"
    template_name = f"{module_slug}.{class_name}"
    paths = owl_asset_paths(module_slug, action_slug, "client_actions")
    docs = owl_docs(owl_version)
    hook_import = '\nimport { useService } from "@web/core/utils/hooks";' if services else ""

    js = f'''import {{ Component, useState }} from "@odoo/owl";
import {{ registry }} from "@web/core/registry";{hook_import}

export class {class_name} extends Component {{
    static template = "{template_name}";
    static props = ["*"];

    setup() {{
        this.state = useState({{ loaded: true }});
{owl_service_setup_lines(services)}
    }}
}}

registry.category("actions").add({js_string(tag)}, {class_name});
'''

    xml_template = f'''<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">
    <t t-name="{template_name}">
        <div class="o_{action_slug} o_action">
            <h2>{xml_text(action_name)}</h2>
            <p>Client action tag: <code>{xml_text(tag)}</code></p>
        </div>
    </t>
</templates>'''

    action_xml = f'''<odoo>
    <record id="action_{action_slug}" model="ir.actions.client">
        <field name="name">{xml_text(action_name)}</field>
        <field name="tag">{xml_text(tag)}</field>
    </record>
</odoo>'''

    scss = f'''.o_{action_slug} {{
    padding: 1rem;
}}'''

    return f"""# OWL Client Action Scaffold: `{class_name}` (Odoo {owl_version})

## JS

```js
{js}
```

## XML Template

```xml
{xml_template}
```

## Action XML

```xml
{action_xml}
```

## SCSS

```scss
{scss}
```

## Manifest Assets

```python
{owl_manifest_asset_snippet(target_bundle, paths)}
```

## Guardrails

- The `ir.actions.client` `tag` must match `registry.category("actions").add({js_string(tag)}, {class_name})`.
- Use `props.action.params` for action parameters instead of hard-coding context.
- Add a menu only under a real parent menu XML ID.

## References

- Registries: {docs['registries']}
- Assets: {docs['assets']}
- Frontend testing: {docs['testing']}
"""


def create_owl_field_widget(
    widget_name: str,
    module_name: str,
    supported_types: list[str] | None = None,
    target_bundle: str = "web.assets_backend",
    version: str = "",
) -> str:
    """Generate an Odoo OWL field widget scaffold using standardFieldProps."""
    owl_version = version if version in ODOO_VERSIONS else current_version["value"]
    module_slug = snake_identifier(module_name, "custom_module")
    widget_slug = snake_identifier(widget_name, "field_widget")
    class_name = pascal_identifier(widget_name, "FieldWidget")
    template_name = f"{module_slug}.{class_name}"
    paths = owl_asset_paths(module_slug, widget_slug, "fields")
    docs = owl_docs(owl_version)
    types = normalized_string_list(supported_types, ["char"])

    js = f'''import {{ Component }} from "@odoo/owl";
import {{ registry }} from "@web/core/registry";
import {{ standardFieldProps }} from "@web/views/fields/standard_field_props";

export class {class_name} extends Component {{
    static template = "{template_name}";
    static props = {{ ...standardFieldProps }};

    get value() {{
        return this.props.record.data[this.props.name];
    }}

    async updateValue(ev) {{
        await this.props.record.update({{ [this.props.name]: ev.target.value }});
    }}
}}

export const {camel_identifier(widget_name)}Field = {{
    component: {class_name},
    displayName: "{class_name}",
    supportedTypes: {js_string_array(types)},
}};

registry.category("fields").add({js_string(widget_slug)}, {camel_identifier(widget_name)}Field);
'''

    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">
    <t t-name="{template_name}">
        <span t-if="props.readonly" t-esc="value"/>
        <input t-else="" class="form-control" t-att-value="value || ''" t-on-change="updateValue"/>
    </t>
</templates>'''

    scss = f'''.o_field_widget[name="{widget_slug}"] {{
    min-width: 8rem;
}}'''

    return f"""# OWL Field Widget Scaffold: `{widget_slug}` (Odoo {owl_version})

## Usage In XML Views

```xml
<field name="your_field" widget="{widget_slug}"/>
```

## JS

```js
{js}
```

## XML Template

```xml
{xml}
```

## SCSS

```scss
{scss}
```

## Manifest Assets

```python
{owl_manifest_asset_snippet(target_bundle, paths)}
```

## Guardrails

- Use `standardFieldProps`; do not invent field prop contracts.
- Read field values from `props.record.data[props.name]`.
- Update values through `props.record.update(...)` so the form/list model stays consistent.
- Restrict `supportedTypes` to field types you actually handle.

## References

- OWL components: {docs['owl']}
- Registries: {docs['registries']}
"""


def create_owl_service(
    service_name: str,
    module_name: str,
    dependencies: list[str] | None = None,
    target_bundle: str = "web.assets_backend",
    version: str = "",
) -> str:
    """Generate an Odoo frontend service scaffold for the services registry."""
    owl_version = version if version in ODOO_VERSIONS else current_version["value"]
    module_slug = snake_identifier(module_name, "custom_module")
    service_slug = snake_identifier(service_name, "custom_service")
    service_const = f"{camel_identifier(service_name)}Service"
    service_path = f"{module_slug}/static/src/services/{service_slug}_service.js"
    docs = owl_docs(owl_version)
    deps = normalized_string_list(dependencies)
    dependency_lines = "\n".join(
        f'        const {camel_identifier(dep)} = services["{dep}"];' for dep in deps
    ) or "        // Access declared dependencies from the `services` object."

    js = f'''import {{ registry }} from "@web/core/registry";

export const {service_const} = {{
    dependencies: {js_string_array(deps)},

    start(env, services) {{
{dependency_lines}

        return {{
            async run(payload = {{}}) {{
                // Implement service behavior here.
                return payload;
            }},
        }};
    }},
}};

registry.category("services").add({js_string(service_slug)}, {service_const});
'''

    return f"""# OWL Service Scaffold: `{service_slug}` (Odoo {owl_version})

## File

- `static/src/services/{service_slug}_service.js`

## JS

```js
{js}
```

## Manifest Assets

```python
{owl_manifest_asset_snippet(target_bundle, [service_path])}
```

## Usage From A Component

```js
import {{ useService }} from "@web/core/utils/hooks";

setup() {{
    this.{camel_identifier(service_name)} = useService({js_string(service_slug)});
}}
```

## Guardrails

- Declare every service dependency in `dependencies`; do not read undeclared services from `env`.
- Keep services stateful only when the state is genuinely shared across components.
- Return a narrow public API from `start(...)`.

## References

- Services: {docs['services']}
- Registries: {docs['registries']}
- Assets: {docs['assets']}
"""


def create_owl_test(
    component_name: str,
    module_name: str,
    test_type: str = "component",
    target_bundle: str = "web.assets_unit_tests",
    version: str = "",
) -> str:
    """Generate an Odoo frontend test scaffold for an OWL component or client action."""
    owl_version = version if version in ODOO_VERSIONS else current_version["value"]
    module_slug = snake_identifier(module_name, "custom_module")
    component_slug = snake_identifier(component_name, "component")
    class_name = pascal_identifier(component_name, "OwlComponent")
    test_slug = snake_identifier(test_type, "component")
    test_path = f"{module_slug}/static/tests/{test_slug}/{component_slug}.test.js"
    docs = owl_docs(owl_version)

    js = f'''import {{ expect, test }} from "@odoo/hoot";
import {{ mountWithCleanup }} from "@web/../tests/web_test_helpers";

import {{ {class_name} }} from "../../src/components/{component_slug}/{component_slug}";

test("{class_name} renders", async () => {{
    const component = await mountWithCleanup({class_name});

    expect(component.el).toHaveText(/Component ready/);
}});
'''

    return f"""# OWL Test Scaffold: `{class_name}` (Odoo {owl_version})

## File

- `static/tests/{test_slug}/{component_slug}.test.js`

## JS Test

```js
{js}
```

## Manifest Test Assets

```python
{owl_manifest_asset_snippet(target_bundle, [test_path])}
```

## Test Checklist

- Assert visible behavior after rendering.
- Add `props` to `mountWithCleanup` only when the component explicitly declares them.
- Mock services/RPCs instead of calling a real server from unit tests.
- Add a WebClient/client-action test when routing, breadcrumbs, or action params matter.
- Add a tour only when browser-level integration is the real risk.

## References

- Frontend testing: {docs['testing']}
- OWL components: {docs['owl']}
- Assets: {docs['assets']}
"""
