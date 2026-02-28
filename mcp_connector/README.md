# MCP Server - AI Integration for Odoo 19

This addon provides an installable MCP backbone for Odoo with:

- MCP server governance configuration (`mcp.server`)
- AI tool registry + execution (`mcp.agent.tool`)
- conversation memory (`mcp.memory.context`)
- audit logs (`mcp.activity.log`)
- dashboard registry (`mcp.echart.dashboard`)
- generated web app registry + route (`mcp.webapp`)
- JSON-RPC entrypoint (`/mcp/jsonrpc`)
- cleanup cron for retention policy

## Main menus

- MCP / Dashboards
- MCP / Web Apps
- MCP / Memory
- MCP / Activity Logs
- MCP / Configuration / Servers
- MCP / Configuration / Tools

## Notes

- Configure `Allowed Models` on active MCP server before executing tools.
- Rate limiting is enforced per user over a one-minute window.
- The module is designed as a base that can be extended with AI agent wiring (`ai.agent`, `ai.tool`) in deployments where Odoo AI modules are available.
