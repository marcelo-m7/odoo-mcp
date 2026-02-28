from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.osv.expression import Domain


class McpAgentTool(models.Model):
    _name = "mcp.agent.tool"
    _description = "MCP Agent Tool"
    _order = "sequence, id"

    name = fields.Char(required=True)
    technical_name = fields.Char(required=True)
    model_name = fields.Char(required=True)
    description = fields.Text()
    method_name = fields.Char(required=True)
    return_schema = fields.Json(default=dict)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    group_ids = fields.Many2many("res.groups", string="Allowed Groups")

    _tool_uniq = models.Constraint("UNIQUE(technical_name)", "Tool technical name must be unique.")

    def _check_group_access(self):
        self.ensure_one()
        if not self.group_ids:
            return True
        if self.group_ids & self.env.user.groups_id:
            return True
        raise AccessError("You do not have the permissions required to use this tool.")

    def _get_payload_value(self, payload, key, default=None):
        if payload is None:
            return default
        return payload.get(key, default)

    def execute(self, payload=None):
        self.ensure_one()
        payload = payload or {}
        self._check_group_access()

        server = self.env["mcp.server"]._get_active_server()
        if not server:
            raise UserError("No active MCP server configured.")
        server.check_rate_limit(self.env.user)

        handler_name = f"_execute_{self.technical_name}"
        if hasattr(self, handler_name):
            return getattr(self, handler_name)(payload)
        raise UserError(f"Tool '{self.technical_name}' is not implemented.")

    def _execute_search_records(self, payload):
        model_name = self._get_payload_value(payload, "model")
        if not model_name:
            raise UserError("Missing model in payload.")

        server = self.env["mcp.server"]._get_active_server()
        if not server.is_model_allowed(model_name):
            raise AccessError("Model is not allowed for MCP operations.")

        limit = int(self._get_payload_value(payload, "limit", 20))
        fields_list = self._get_payload_value(payload, "fields", ["display_name"])
        domain = Domain(self._get_payload_value(payload, "domain", []))

        records = self.env[model_name].search(domain, limit=limit)
        return records.read(fields_list)

    def _execute_create_record(self, payload):
        model_name = self._get_payload_value(payload, "model")
        values = self._get_payload_value(payload, "values", {})

        server = self.env["mcp.server"]._get_active_server()
        if not server.is_model_allowed(model_name):
            raise AccessError("Model is not allowed for MCP operations.")
        if server.approval_required:
            return self._create_approval("create", payload)

        record = self.env[model_name].create(values)
        return {"id": record.id, "display_name": record.display_name}

    def _execute_update_record(self, payload):
        model_name = self._get_payload_value(payload, "model")
        record_id = int(self._get_payload_value(payload, "id", 0))
        values = self._get_payload_value(payload, "values", {})

        server = self.env["mcp.server"]._get_active_server()
        if not server.is_model_allowed(model_name):
            raise AccessError("Model is not allowed for MCP operations.")
        if server.approval_required:
            return self._create_approval("update", payload)

        record = self.env[model_name].browse(record_id).exists()
        if not record:
            raise UserError("Record not found.")

        record.write(values)
        return {"id": record.id, "display_name": record.display_name}

    def _execute_delete_record(self, payload):
        model_name = self._get_payload_value(payload, "model")
        record_id = int(self._get_payload_value(payload, "id", 0))

        server = self.env["mcp.server"]._get_active_server()
        if not server.is_model_allowed(model_name):
            raise AccessError("Model is not allowed for MCP operations.")
        if server.approval_required:
            return self._create_approval("delete", payload)

        record = self.env[model_name].browse(record_id).exists()
        if not record:
            raise UserError("Record not found.")

        record.unlink()
        return {"deleted": True, "id": record_id}

    def _execute_generate_dashboard(self, payload):
        dashboard = self.env["mcp.echart.dashboard"].create({
            "name": self._get_payload_value(payload, "name", "Generated Dashboard"),
            "model_source": self._get_payload_value(payload, "model", "res.partner"),
            "query": self._get_payload_value(payload, "domain", []),
            "options": self._get_payload_value(payload, "options", {}),
            "code": self._get_payload_value(payload, "code", ""),
        })
        return {"dashboard_id": dashboard.id, "name": dashboard.name}

    def _execute_generate_web_app(self, payload):
        webapp = self.env["mcp.webapp"].create({
            "name": self._get_payload_value(payload, "name", "Generated Web App"),
            "slug": self._get_payload_value(payload, "slug", f"app-{fields.Datetime.now().timestamp():.0f}"),
            "code_js": self._get_payload_value(payload, "code_js", "export default function App() { return <div>Hello MCP</div>; }"),
            "endpoints": self._get_payload_value(payload, "endpoints", []),
            "public_access": bool(self._get_payload_value(payload, "public_access", False)),
        })
        return {"webapp_id": webapp.id, "url": webapp.full_url}

    def _create_approval(self, operation, payload):
        approval = self.env["mcp.approval"].create({
            "operation": operation,
            "requester_id": self.env.user.id,
            "tool_id": self.id,
            "payload": payload,
        })
        return {"queued_for_approval": True, "approval_id": approval.id}


class AiTool(models.Model):
    _inherit = "ai.tool"

    mcp_tool_id = fields.Many2one("mcp.agent.tool", string="MCP Tool")

    @api.model
    def _mcp_execute(self, tool_name, payload):
        tool = self.env["mcp.agent.tool"].search([
            ("technical_name", "=", tool_name),
            ("active", "=", True),
        ], limit=1)
        if not tool:
            raise UserError("MCP tool not found.")
        return tool.execute(payload)
