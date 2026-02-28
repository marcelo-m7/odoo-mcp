import time

from odoo import http
from odoo.http import request


class McpJsonRpcController(http.Controller):

    @http.route("/mcp/jsonrpc", type="jsonrpc", auth="user", methods=["POST"], csrf=False)
    def mcp_jsonrpc(self, tool_name=None, payload=None, **kwargs):
        start = time.time()
        status = "success"
        response = {}
        error_message = False

        try:
            tool = request.env["mcp.agent.tool"].sudo().search([
                ("technical_name", "=", tool_name),
                ("active", "=", True),
            ], limit=1)
            if not tool:
                raise ValueError("Tool not found or inactive")
            response = tool.with_user(request.env.user).execute(payload)
            return response
        except Exception as exc:  # pylint: disable=broad-exception-caught
            status = "failed"
            error_message = str(exc)
            raise
        finally:
            request.env["mcp.activity.log"].sudo().create({
                "user_id": request.env.user.id,
                "tool_id": request.env["mcp.agent.tool"].sudo().search([
                    ("technical_name", "=", tool_name),
                ], limit=1).id,
                "request_payload": payload or {},
                "response_payload": response if isinstance(response, dict | list) else {"value": str(response)},
                "status": status,
                "duration_ms": int((time.time() - start) * 1000),
                "error_message": error_message,
            })
