import json

from odoo import api, fields, models


class McpMemoryContext(models.Model):
    _name = "mcp.memory.context"
    _description = "MCP Memory Context"

    name = fields.Char(compute="_compute_name", store=True)
    user_id = fields.Many2one("res.users", required=True, index=True)
    messages = fields.Text(default="[]")
    created_at = fields.Datetime(default=fields.Datetime.now)
    updated_at = fields.Datetime(default=fields.Datetime.now)

    @api.depends("user_id")
    def _compute_name(self):
        for record in self:
            record.name = f"Memory for {record.user_id.display_name}"

    @api.constrains("messages")
    def _check_messages_json(self):
        for record in self:
            json.loads(record.messages or "[]")

    def append_message(self, role, content):
        self.ensure_one()
        messages = json.loads(self.messages or "[]")
        messages.append({"role": role, "content": content})
        self.write({"messages": json.dumps(messages), "updated_at": fields.Datetime.now()})
