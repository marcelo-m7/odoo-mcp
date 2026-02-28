{
    "name": "MCP Server - AI Integration for Odoo 19",
    "version": "1.0.0",
    "summary": "Secure MCP layer with AI tools, dashboards, web-app generator, and governance controls.",
    "description": """
MCP Connector for Odoo 19
=========================

This module provides:
* MCP server configuration and model allow-listing
* Tool registry for AI-safe CRUD and generation operations
* JSON-RPC endpoint for MCP clients
* Dashboard and web-app generation records
* Approval workflow, audit logs, and retention cron
    """,
    "author": "Marcelo Santos",
    "company": "Corvanis",
    "category": "Tools",
    "license": "LGPL-3",
    "depends": ["base", "mail", "web", "website", "portal", "ai"],
    "data": [
        "security/mcp_groups.xml",
        "security/ir.model.access.csv",
        "views/mcp_server_views.xml",
        "views/mcp_tool_views.xml",
        "views/mcp_dashboard_views.xml",
        "views/mcp_webapp_views.xml",
        "views/mcp_approval_views.xml",
        "views/mcp_activity_views.xml",
        "views/mcp_menu.xml",
        "views/mcp_templates.xml",
        "data/mcp_tool_data.xml",
        "data/mcp_cron_data.xml"
    ],
    "installable": True,
    "application": True,
}
