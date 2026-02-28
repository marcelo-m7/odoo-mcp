import json

from odoo import api, fields, models


class McpWebApp(models.Model):
    _name = "mcp.webapp"
    _description = "MCP Generated Web Application"

    name = fields.Char(required=True)
    slug = fields.Char(required=True)
    code_js = fields.Text(required=True)
    endpoints = fields.Text(default="[]")
    group_ids = fields.Many2many("res.groups", string="Allowed Groups")
    public_access = fields.Boolean(default=False)

    _sql_constraints = [
        models.Constraint("mcp_webapp_slug_unique", "unique(slug)", "Slug must be unique."),
    ]

    @api.constrains("endpoints")
    def _check_endpoints_json(self):
        for record in self:
            json.loads(record.endpoints or "[]")
