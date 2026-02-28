from odoo import api, fields, models


class McpActivityLog(models.Model):
    _name = "mcp.activity.log"
    _description = "MCP Activity Log"
    _order = "request_time desc"

    request_time = fields.Datetime(default=fields.Datetime.now, required=True)
    user_id = fields.Many2one("res.users", ondelete="set null")
    tool_id = fields.Many2one("mcp.agent.tool", ondelete="set null")
    request_payload = fields.Json(default=dict)
    response_payload = fields.Json(default=dict)
    status = fields.Selection([
        ("success", "Success"),
        ("failed", "Failed"),
    ], default="success", required=True)
    duration_ms = fields.Integer(default=0)
    error_message = fields.Text()

    @api.model
    def _cron_cleanup_old_logs(self):
        limit_date = fields.Datetime.subtract(fields.Datetime.now(), days=30)
        self.search([("request_time", "<", limit_date)]).unlink()
