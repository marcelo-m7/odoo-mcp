from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError


class McpServer(models.Model):
    _name = "mcp.server"
    _description = "MCP Server Configuration"
    _order = "name"

    name = fields.Char(required=True)
    url = fields.Char(required=True)
    active = fields.Boolean(default=True)
    approval_required = fields.Boolean(default=False)
    rate_limit = fields.Integer(default=120)
    allowed_model_ids = fields.Many2many("ir.model", string="Allowed Models")
    manager_group_id = fields.Many2one("res.groups", string="Manager Group")

    _name_unique = models.Constraint("UNIQUE(name)", "Server name must be unique.")

    @api.model
    def _get_active_server(self):
        return self.search([("active", "=", True)], limit=1)

    def check_rate_limit(self, user):
        self.ensure_one()
        if user.has_group("base.group_system"):
            return True

        since = fields.Datetime.now() - timedelta(minutes=1)
        count = self.env["mcp.activity.log"].search_count([
            ("user_id", "=", user.id),
            ("request_time", ">=", since),
        ])
        if count >= self.rate_limit:
            raise AccessError("Rate limit exceeded. Please retry in a minute.")
        return True

    def is_model_allowed(self, model_name):
        self.ensure_one()
        return model_name in self.allowed_model_ids.mapped("model")
