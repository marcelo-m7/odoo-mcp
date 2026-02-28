# MCP Connector (Odoo 19)

This addon provides an MCP-ready application for Odoo 19 with:

- MCP server configuration and model allow-listing (`mcp.server`)
- AI tool registry and execution handlers (`mcp.agent.tool`)
- JSON-RPC endpoint at `/mcp/jsonrpc`
- Governance objects: audit logs, memory contexts, approval requests
- Generated assets support: dashboards and web apps
- Website route for generated web apps at `/mcp/webapp/<slug>`

## Main menus

- MCP Studio / Configuration
- MCP Studio / Assets
- MCP Studio / Governance

## Notes

- Depends on Odoo AI module (`ai`) for tool integration model extension.
- Includes default MCP tools and a daily retention cron for logs.
