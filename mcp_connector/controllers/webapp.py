from odoo import http
from odoo.http import request


class McpWebappController(http.Controller):

    @http.route("/mcp/webapp/<string:slug>", type="http", auth="public", website=True)
    def mcp_webapp(self, slug, **kwargs):
        webapp = request.env["mcp.webapp"].sudo().search([
            ("slug", "=", slug),
            ("active", "=", True),
        ], limit=1)
        if not webapp:
            return request.not_found()

        if not webapp.public_access and request.env.user._is_public():
            return request.redirect("/web/login")

        if webapp.group_ids and not (webapp.group_ids & request.env.user.groups_id):
            return request.render("website.403")

        return request.render("mcp_connector.webapp_page", {"webapp": webapp})
