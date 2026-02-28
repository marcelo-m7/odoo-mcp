from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestMcpModels(TransactionCase):
    def test_server_constraint(self):
        server = self.env["mcp.server"].create({
            "name": "Default",
            "url": "http://localhost:8069/mcp/jsonrpc",
            "rate_limit": 20,
            "retention_days": 30,
        })
        self.assertTrue(server.active)

    def test_tool_exec_search(self):
        model = self.env["ir.model"].search([("model", "=", "res.partner")], limit=1)
        server = self.env["mcp.server"].create({
            "name": "Server2",
            "url": "http://localhost",
            "allowed_model_ids": [(4, model.id)],
            "rate_limit": 100,
        })
        tool = self.env["mcp.agent.tool"].create({
            "name": "search_test",
            "model": "res.partner",
            "method": "search_records",
        })
        result = tool.execute_tool({"limit": 1})
        self.assertIn("ids", result)
        self.assertTrue(server)
