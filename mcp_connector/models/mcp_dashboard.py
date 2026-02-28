from odoo import fields, models


class McpEchartDashboard(models.Model):
    _name = "mcp.echart.dashboard"
    _description = "MCP EChart Dashboard"

    name = fields.Char(required=True)
    model_source = fields.Char(required=True)
    query = fields.Json(default=list)
    options = fields.Json(default=dict)
    code = fields.Text()
    media_queries = fields.Json(default=dict)
    user_ids = fields.Many2many("res.users", string="Shared Users")
    group_ids = fields.Many2many("res.groups", string="Shared Groups")
    active = fields.Boolean(default=True)

    _name_unique = models.Constraint("UNIQUE(name)", "Dashboard name must be unique.")
