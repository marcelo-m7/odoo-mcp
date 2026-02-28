from odoo import http
from odoo.http import request


class McpWebAppController(http.Controller):
    @http.route(["/mcp/webapp/<string:slug>"], type="http", auth="public", website=True)
    def webapp(self, slug, **kwargs):
        app = request.env["mcp.webapp"].sudo().search([("slug", "=", slug)], limit=1)
        if not app:
            return request.not_found()

        if not app.public_access and request.env.user._is_public():
            return request.redirect("/web/login")

        if app.group_ids and not (app.group_ids & request.env.user.groups_id):
            return request.render("website.403")

        html = f"""
            <html>
                <head>
                    <title>{app.name}</title>
                    <meta name='viewport' content='width=device-width, initial-scale=1.0'/>
                </head>
                <body>
                    <div id='mcp-webapp-root'></div>
                    <script type='module'>
                        {app.code_js}
                    </script>
                </body>
            </html>
        """
        return request.make_response(html)
