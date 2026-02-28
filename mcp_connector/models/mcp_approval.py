from odoo import fields, models
from odoo.exceptions import AccessError


class McpApproval(models.Model):
    _name = "mcp.approval"
    _description = "MCP Approval Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    operation = fields.Selection([
        ("create", "Create"),
        ("update", "Update"),
        ("delete", "Delete"),
    ], required=True)
    requester_id = fields.Many2one("res.users", required=True)
    approver_id = fields.Many2one("res.users")
    tool_id = fields.Many2one("mcp.agent.tool", required=True)
    payload = fields.Json(default=dict)
    state = fields.Selection([
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("executed", "Executed"),
    ], default="pending", required=True, tracking=True)
    rejection_reason = fields.Text()

    def action_approve(self):
        for record in self:
            record._check_approver_permissions()
            record.state = "approved"
            record.approver_id = self.env.user

    def action_reject(self):
        for record in self:
            record._check_approver_permissions()
            record.state = "rejected"
            record.approver_id = self.env.user

    def _check_approver_permissions(self):
        if not self.env.user.has_group("mcp_connector.group_mcp_manager"):
            raise AccessError("Only MCP managers can process approvals.")
