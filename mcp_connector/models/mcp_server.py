from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError


class McpServer(models.Model):
    _name = "mcp.server"
    _description = "MCP Server Configuration"

    name = fields.Char(required=True)
    url = fields.Char(required=True)
    allowed_model_ids = fields.Many2many("ir.model", string="Allowed Models")
    approval_required = fields.Boolean(default=False)
    rate_limit = fields.Integer(default=60, help="Requests per minute per user.")
    retention_days = fields.Integer(default=90)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        models.Constraint("mcp_server_name_unique", "unique(name)", "Server name must be unique."),
    ]

    @api.constrains("rate_limit", "retention_days")
    def _check_positive_limits(self):
        for server in self:
            if server.rate_limit < 1:
                raise ValidationError("Rate limit must be at least 1 request per minute.")
            if server.retention_days < 1:
                raise ValidationError("Retention days must be at least 1 day.")

    def _is_model_allowed(self, model_name):
        self.ensure_one()
        return model_name in self.allowed_model_ids.mapped("model")

    def check_rate_limit(self, user):
        self.ensure_one()
        one_minute_ago = fields.Datetime.subtract(fields.Datetime.now(), minutes=1)
        usage_count = self.env["mcp.activity.log"].search_count([
            ("user_id", "=", user.id),
            ("create_date", ">=", one_minute_ago),
        ])
        if usage_count >= self.rate_limit:
            raise AccessError("Rate limit exceeded for MCP requests.")

    @api.model
    def _cron_cleanup_old_logs(self):
        servers = self.search([])
        for server in servers:
            expiry = fields.Datetime.subtract(fields.Datetime.now(), days=server.retention_days)
            self.env["mcp.activity.log"].search([
                ("create_date", "<", expiry),
            ]).unlink()
            self.env["mcp.memory.context"].search([
                ("write_date", "<", expiry),
            ]).unlink()
