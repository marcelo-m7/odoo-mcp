from odoo import http
from odoo.http import request


class McpJsonRpcController(http.Controller):
    @http.route("/mcp/jsonrpc", type="jsonrpc", auth="user", methods=["POST"], csrf=False)
    def jsonrpc(self, tool_name=None, payload=None, **kwargs):
        tool = request.env["mcp.agent.tool"].sudo().search([
            ("name", "=", tool_name),
            ("active", "=", True),
        ], limit=1)
        if not tool:
            return {"error": "Tool not found"}
        result = tool.with_user(request.env.user).execute_tool(payload or {})
        return {"result": result}
