from odoo import fields, models


class McpActivityLog(models.Model):
    _name = "mcp.activity.log"
    _description = "MCP Activity Log"
    _order = "create_date desc"

    timestamp = fields.Datetime(default=fields.Datetime.now)
    user_id = fields.Many2one("res.users", required=True, index=True)
    tool_id = fields.Many2one("mcp.agent.tool", index=True)
    request_payload = fields.Text()
    response_payload = fields.Text()
    status = fields.Selection(
        selection=[("success", "Success"), ("failed", "Failed")],
        default="success",
        required=True,
    )
    duration_ms = fields.Integer(default=0)
