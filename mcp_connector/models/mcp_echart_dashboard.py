import json

from odoo import api, fields, models


class McpEchartDashboard(models.Model):
    _name = "mcp.echart.dashboard"
    _description = "MCP EChart Dashboard"

    name = fields.Char(required=True)
    model_source = fields.Char(required=True)
    query = fields.Text(default="[]")
    options = fields.Text(default="{}")
    code = fields.Text()
    shared_user_ids = fields.Many2many("res.users", string="Shared with Users")
    shared_group_ids = fields.Many2many("res.groups", string="Shared with Groups")
    media_queries = fields.Text(default="{}")

    _sql_constraints = [
        models.Constraint("mcp_echart_dashboard_name_unique", "unique(name)", "Dashboard name must be unique."),
    ]

    @api.constrains("query", "options", "media_queries")
    def _check_json_fields(self):
        for record in self:
            json.loads(record.query or "[]")
            json.loads(record.options or "{}")
            json.loads(record.media_queries or "{}")
