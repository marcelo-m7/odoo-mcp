from odoo import api, fields, models


class McpWebapp(models.Model):
    _name = "mcp.webapp"
    _description = "MCP Generated Web App"

    name = fields.Char(required=True)
    slug = fields.Char(required=True)
    code_js = fields.Text(required=True)
    endpoints = fields.Json(default=list)
    group_ids = fields.Many2many("res.groups", string="Allowed Groups")
    public_access = fields.Boolean(default=False)
    active = fields.Boolean(default=True)
    full_url = fields.Char(compute="_compute_full_url")

    _slug_unique = models.Constraint("UNIQUE(slug)", "Web app slug must be unique.")

    @api.depends("slug")
    def _compute_full_url(self):
        base = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        for record in self:
            record.full_url = f"{base}/mcp/webapp/{record.slug}" if base else f"/mcp/webapp/{record.slug}"
