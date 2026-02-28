from odoo import fields, models


class McpMemoryContext(models.Model):
    _name = "mcp.memory.context"
    _description = "MCP Conversation Memory"
    _order = "write_date desc"

    user_id = fields.Many2one("res.users", required=True, ondelete="cascade")
    messages = fields.Json(default=list)
    summary = fields.Text()
