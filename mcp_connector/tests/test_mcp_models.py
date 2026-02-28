from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestMcpModels(TransactionCase):

    def test_server_creation(self):
        server = self.env["mcp.server"].create({
            "name": "Test Server",
            "url": "/mcp/jsonrpc",
        })
        self.assertTrue(server.active)

    def test_webapp_url(self):
        webapp = self.env["mcp.webapp"].create({
            "name": "Test App",
            "slug": "test-app",
            "code_js": "console.log('ok')",
        })
        self.assertIn("/mcp/webapp/test-app", webapp.full_url)
