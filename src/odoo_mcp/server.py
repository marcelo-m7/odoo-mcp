from __future__ import annotations

import sys
import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from .domains.addons import facade as addon_facade
from .domains.diagnostics import facade as diagnostic_facade
from .domains.docs import facade as docs_facade
from .domains.environment import facade as environment_facade
from .domains.environment.local_context import configured_env_value
from .domains.planning import facade as planning_facade
from .domains.scaffolds import facade as scaffold_facade
from .domains.source import facade as source_facade
from .runtime.paths import DOCS_BASE_PATH, RULES_BASE_PATH
from .runtime.state import ODOO_VERSIONS, current_version
from .schemas.addon_context import AddonContextRequest
from .schemas.source_inspection import SourceInspectionRequest
from .schemas.version import VersionDetectionRequest


def build_mcp() -> FastMCP:
    """Use local stdio by default; hosted HTTP cannot exist without OAuth."""
    transport = os.environ.get("ODOO_MCP_TRANSPORT", "stdio")
    if transport != "streamable-http":
        if transport != "stdio":
            raise ValueError("ODOO_MCP_TRANSPORT must be stdio or streamable-http")
        return FastMCP("Odoo Development Assistant")

    from urllib.parse import urlsplit

    from mcp.server.auth.settings import AuthSettings
    from mcp.server.transport_security import TransportSecuritySettings
    from pydantic import AnyHttpUrl

    from .hosted_auth import HostedConfig, IntrospectionTokenVerifier

    config = HostedConfig.from_env()
    domain = urlsplit(config.resource_url).hostname
    return FastMCP(
        "Monynha Odoo MCP",
        stateless_http=True,
        json_response=True,
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(config.issuer_url),
            resource_server_url=AnyHttpUrl(config.resource_url),
            required_scopes=[config.scope],
        ),
        token_verifier=IntrospectionTokenVerifier(config),
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=[domain, f"{domain}:*", "localhost:*", "127.0.0.1:*"],
            allowed_origins=[f"https://{domain}", "https://chatgpt.com"],
        ),
    )


mcp = build_mcp()


def _register_optional_operations() -> None:
    """Keep all existing development features working with operations disabled."""
    if os.environ.get("ODOO_MCP_OPERATIONS_ENABLED") != "1":
        return
    from .operations.backends import make_backend
    from .operations.config import ConnectionRegistry, EnvironmentCredentials
    from .operations.policy import Policy
    from .operations.registration import register_operations
    from .operations.service import OdooService

    registry = ConnectionRegistry.from_json(
        os.environ.get("ODOO_MCP_CONNECTIONS_JSON", ""),
        allow_local=os.environ.get("ODOO_MCP_ALLOW_LOCAL") == "1",
    )
    credentials = EnvironmentCredentials()
    policy = Policy.from_json(os.environ.get("ODOO_MCP_WRITE_POLICY_JSON"))
    backends = {}

    def backend_for(connection):
        if connection.id not in backends:
            backends[connection.id] = make_backend(connection, credentials)
        return backends[connection.id]

    register_operations(mcp, OdooService(registry, backend_for, policy), registry)

get_all_rst_files = docs_facade.get_all_rst_files
normalize_reference_path = docs_facade.normalize_reference_path
get_reference_fragment = docs_facade.get_reference_fragment
get_reference_target = docs_facade.get_reference_target
get_all_reference_topics = docs_facade.get_all_reference_topics
get_official_documentation_url = docs_facade.get_official_documentation_url
get_reference_topics = docs_facade.get_reference_topics
find_reference_topic = docs_facade.find_reference_topic
get_skill_informed_guidance = planning_facade.get_skill_informed_guidance
get_odoo_local_context_content = environment_facade.get_odoo_local_context


@mcp.resource("odoo://local/context")
def get_odoo_local_context_resource() -> str:
    return environment_facade.get_odoo_local_context(include_readme_excerpt=True)


@mcp.resource("odoo://docs/{version}/index")
def get_documentation_index(version: str) -> str:
    return docs_facade.get_documentation_index(version)


@mcp.resource("odoo://docs/{version}/{path}")
def get_documentation_content(version: str, path: str) -> str:
    return docs_facade.get_documentation_content(version, path)


@mcp.resource("odoo://rules/{rule_name}")
def get_development_rules(rule_name: str) -> str:
    return planning_facade.get_development_rules(rule_name)


@mcp.tool()
def set_odoo_version(version: str) -> str:
    if version not in ODOO_VERSIONS:
        return f"Invalid version. Available versions: {', '.join(ODOO_VERSIONS)}"

    current_version["value"] = version
    return f"Odoo version set to {version}"


@mcp.tool()
def get_current_version() -> str:
    return f"Current Odoo development version: {current_version['value']}"


@mcp.tool()
def detect_odoo_version(
    path: str = "",
    include_env: bool = True,
    include_source: bool = True,
    include_manifests: bool = True,
    include_branch: bool = True,
) -> str:
    request = VersionDetectionRequest(
        path=path,
        include_env=include_env,
        include_source=include_source,
        include_manifests=include_manifests,
        include_branch=include_branch,
    )
    return environment_facade.detect_odoo_version(request)


@mcp.tool()
def inspect_odoo_source(
    path: str = "",
    query: str = "",
    scope: str = "both",
    max_files: int = 200,
) -> str:
    request = SourceInspectionRequest(path=path, query=query, scope=scope, max_files=max_files)
    return source_facade.inspect_odoo_source(request, env_source=configured_env_value("ODOO_SOURCE"))


@mcp.tool()
def read_odoo_addon_context(
    addon: str,
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
) -> str:
    request = AddonContextRequest(
        addon=addon,
        addons_path=addons_path,
        path=path,
        odoo_config=odoo_config,
        include=include,
        exclude_addons=exclude_addons,
        no_exclude_addons=no_exclude_addons,
        shrink_mode=shrink_mode,
        expand_models=expand_models,
        add_expand_models=add_expand_models,
        rm_expand_models=rm_expand_models,
        expand_methods=expand_methods,
        auto_expand=auto_expand,
        context_budget_tokens=context_budget_tokens,
        max_files=max_files,
    )
    return addon_facade.read_odoo_addon_context(request, env_source=configured_env_value("ODOO_SOURCE"))


@mcp.tool()
def get_odoo_local_context(include_readme_excerpt: bool = True) -> str:
    return environment_facade.get_odoo_local_context(include_readme_excerpt=include_readme_excerpt)


@mcp.tool()
def get_documentation_url(path: str = "", version: str = "") -> str:
    return docs_facade.get_documentation_url(path=path, version=version)


@mcp.tool()
def search_documentation(query: str, version: str = "") -> str:
    return docs_facade.search_documentation(query=query, version=version)


@mcp.tool()
def get_development_guidelines(context: str = "general") -> str:
    return planning_facade.get_development_guidelines(context=context)


@mcp.tool()
def create_odoo_module(
    module_name: str,
    display_name: str,
    description: str,
    author: str = "Your Company",
    category: str = "Uncategorized",
    depends: list[str] | None = None,
) -> str:
    return scaffold_facade.create_odoo_module(module_name, display_name, description, author, category, depends)


@mcp.tool()
def create_odoo_model(
    model_name: str,
    model_description: str,
    fields: list[dict[str, Any]],
    inherit: str = "",
) -> str:
    return scaffold_facade.create_odoo_model(model_name, model_description, fields, inherit)


@mcp.tool()
def create_odoo_view(
    model_name: str,
    view_type: str,
    fields_to_display: list[str],
    view_name: str = "",
    parent_menu: str = "",
) -> str:
    return scaffold_facade.create_odoo_view(model_name, view_type, fields_to_display, view_name, parent_menu)


@mcp.tool()
def create_security_rules(
    model_name: str,
    module_name: str,
    groups: list[str] | None = None,
) -> str:
    return scaffold_facade.create_security_rules(model_name, module_name, groups)


@mcp.tool()
def create_base_automation(
    automation_name: str,
    model_name: str,
    trigger: str = "on_create_or_write",
    action_type: str = "code",
    code: str = "",
    module_name: str = "",
    model_xml_id: str = "",
    trigger_fields: list[str] | None = None,
    filter_domain: str = "",
    filter_pre_domain: str = "",
    update_path: str = "",
    update_value: str = "",
    update_boolean_value: str = "",
    date_field: str = "",
    date_field_xml_id: str = "",
    delay: int = 0,
    delay_unit: str = "hour",
    delay_mode: str = "after",
    webhook_url: str = "",
    webhook_fields: list[str] | None = None,
    xml_id: str = "",
    noupdate: bool = True,
    version: str = "",
) -> str:
    return scaffold_facade.create_base_automation(
        automation_name, model_name, trigger, action_type, code, module_name, model_xml_id,
        trigger_fields, filter_domain, filter_pre_domain, update_path, update_value, update_boolean_value,
        date_field, date_field_xml_id, delay, delay_unit, delay_mode, webhook_url, webhook_fields,
        xml_id, noupdate, version,
    )


@mcp.tool()
def plan_owl_feature(
    feature_description: str,
    module_name: str,
    integration_type: str = "component",
    target_bundle: str = "web.assets_backend",
    version: str = "",
) -> str:
    return scaffold_facade.plan_owl_feature(feature_description, module_name, integration_type, target_bundle, version)


@mcp.tool()
def create_owl_component(
    component_name: str,
    module_name: str,
    props: list[str] | None = None,
    services: list[str] | None = None,
    use_state: bool = False,
    target_bundle: str = "web.assets_backend",
    version: str = "",
) -> str:
    return scaffold_facade.create_owl_component(component_name, module_name, props, services, use_state, target_bundle, version)


@mcp.tool()
def create_owl_client_action(
    action_name: str,
    module_name: str,
    action_tag: str = "",
    services: list[str] | None = None,
    target_bundle: str = "web.assets_backend",
    version: str = "",
) -> str:
    return scaffold_facade.create_owl_client_action(action_name, module_name, action_tag, services, target_bundle, version)


@mcp.tool()
def create_owl_field_widget(
    widget_name: str,
    module_name: str,
    supported_types: list[str] | None = None,
    target_bundle: str = "web.assets_backend",
    version: str = "",
) -> str:
    return scaffold_facade.create_owl_field_widget(widget_name, module_name, supported_types, target_bundle, version)


@mcp.tool()
def create_owl_service(
    service_name: str,
    module_name: str,
    dependencies: list[str] | None = None,
    target_bundle: str = "web.assets_backend",
    version: str = "",
) -> str:
    return scaffold_facade.create_owl_service(service_name, module_name, dependencies, target_bundle, version)


@mcp.tool()
def create_owl_test(
    component_name: str,
    module_name: str,
    test_type: str = "component",
    target_bundle: str = "web.assets_unit_tests",
    version: str = "",
) -> str:
    return scaffold_facade.create_owl_test(component_name, module_name, test_type, target_bundle, version)


@mcp.tool()
def layout_module_dependencies(
    module_name: str,
    features: list[str] | None = None,
    models: list[str] | None = None,
    integrate_with: list[str] | None = None,
    explicit_dependencies: list[str] | None = None,
    include_transitive: bool = False,
    version: str = "",
) -> str:
    return scaffold_facade.layout_module_dependencies(
        module_name, features, models, integrate_with, explicit_dependencies, include_transitive, version
    )


@mcp.tool()
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
    return scaffold_facade.create_upgrade_script(
        module_name, from_version, to_version, migration_version, rename_models, rename_fields,
        rename_xmlids, data_migrations, oca_style,
    )


@mcp.tool()
def explain_odoo_error(error_text: str, version: str = "", context: str = "") -> str:
    return diagnostic_facade.explain_odoo_error(error_text, version, context)


@mcp.tool()
def plan_odoo_feature(feature_description: str, module_name: str = "", version: str = "") -> str:
    return planning_facade.plan_odoo_feature(feature_description, module_name, version)


@mcp.prompt()
def develop_odoo_feature(feature_description: str) -> str:
    return planning_facade.develop_odoo_feature(feature_description)


@mcp.prompt()
def debug_odoo_error(error_message: str, context: str = "") -> str:
    return planning_facade.debug_odoo_error(error_message, context)


@mcp.prompt()
def upgrade_odoo_module(module_name: str, from_version: str, to_version: str) -> str:
    return planning_facade.upgrade_odoo_module(module_name, from_version, to_version)


@mcp.prompt()
def review_odoo_code(code: str) -> str:
    return planning_facade.review_odoo_code(code)


def main():
    """Run the MCP server with proper error handling."""
    if sys.stdin.isatty():
        print("\n" + "=" * 70, file=sys.stderr)
        print("⚠️  WARNING: MCP Server cannot be run directly from terminal!", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print("\nMCP servers communicate via JSON-RPC over stdin/stdout.", file=sys.stderr)
        print("They must be run through an MCP client.\n", file=sys.stderr)
        print("To TEST the server functionality:", file=sys.stderr)
        print("  python -m tests.test_server\n", file=sys.stderr)
        print("To USE the server:", file=sys.stderr)
        print("  1. Configure in Claude Desktop or OpenCode (see README.md)", file=sys.stderr)
        print("  2. Or use MCP Inspector: mcp dev src/odoo_mcp/server.py\n", file=sys.stderr)
        print("For more information, see:", file=sys.stderr)
        print("  - README.md", file=sys.stderr)
        print("  - guides/QUICK_START.md", file=sys.stderr)
        print("  - guides/OPENCODE_SETUP.md\n", file=sys.stderr)
        sys.exit(1)

    try:
        mcp.run()
    except KeyboardInterrupt:
        print("\nServer stopped by user", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        print(f"\nServer error: {e}", file=sys.stderr)
        sys.exit(1)


_register_optional_operations()


if __name__ == "__main__":
    main()
