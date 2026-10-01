from __future__ import annotations

from html import escape

from ...runtime.state import ODOO_VERSIONS, current_version
from ...utils.formatting import normalized_string_list
from ..docs.facade import get_official_documentation_url

def model_external_id(model_name: str, model_xml_id: str = "") -> str:
    if model_xml_id:
        return model_xml_id
    return f"model_{model_name.replace('.', '_')}"


def field_external_id(model_name: str, field_name: str, module_name: str = "") -> str:
    external_id = f"field_{model_name.replace('.', '_')}__{field_name}"
    return f"{module_name}.{external_id}" if module_name else external_id


def xml_field(name: str, value: str, *, eval_value: bool = False) -> str:
    if eval_value:
        return f'            <field name="{name}" eval="{escape(value, quote=True)}"/>'
    return f'            <field name="{name}">{escape(value)}</field>'


def create_base_automation(
    automation_name: str,
    model_name: str,
    trigger: str = "on_create_or_write",
    action_type: str = "code",
    code: str = "",
    module_name: str = "",
    model_xml_id: str = "",
    trigger_fields: list[str] | None = None,
    filter_domain: str = "",
    filter_pre_domain: str = "",
    update_path: str = "",
    update_value: str = "",
    update_boolean_value: str = "",
    date_field: str = "",
    date_field_xml_id: str = "",
    delay: int = 0,
    delay_unit: str = "hour",
    delay_mode: str = "after",
    webhook_url: str = "",
    webhook_fields: list[str] | None = None,
    xml_id: str = "",
    noupdate: bool = True,
    version: str = "",
) -> str:
    automation_version = version if version in ODOO_VERSIONS else current_version["value"]
    trigger_fields = normalized_string_list(trigger_fields)
    webhook_fields = normalized_string_list(webhook_fields)
    trigger = trigger.strip() or "on_create_or_write"
    action_type = action_type.strip() or "code"
    module_name = module_name.strip()
    model_ref = model_external_id(model_name, model_xml_id.strip())
    xml_stem = xml_id.strip() or f"automation_{model_name.replace('.', '_')}_{trigger}"
    action_xml_id = f"{xml_stem}_action"
    data_noupdate = "1" if noupdate else "0"
    time_triggers = {"on_time", "on_time_created", "on_time_updated"}

    automation_fields = [
        xml_field("name", automation_name),
        f'            <field name="model_id" ref="{escape(model_ref, quote=True)}"/>',
        xml_field("trigger", trigger),
    ]

    if filter_domain:
        automation_fields.append(xml_field("filter_domain", filter_domain))
    if filter_pre_domain:
        automation_fields.append(xml_field("filter_pre_domain", filter_pre_domain))

    if trigger_fields:
        refs = []
        for field in trigger_fields:
            field_ref = field if "." in field else field_external_id(model_name, field, module_name)
            refs.append(f"ref('{field_ref}')")
        automation_fields.append(xml_field("trigger_field_ids", f"[(6, 0, [{', '.join(refs)}])]", eval_value=True))

    if trigger in time_triggers:
        if date_field_xml_id or date_field:
            date_ref = date_field_xml_id or field_external_id(model_name, date_field, module_name)
            automation_fields.append(f'            <field name="trg_date_id" ref="{escape(date_ref, quote=True)}"/>')
        signed_delay = abs(delay)
        if automation_version in {"17.0", "18.0"} and delay_mode == "before":
            signed_delay = -signed_delay
        automation_fields.append(xml_field("trg_date_range", str(signed_delay), eval_value=True))
        automation_fields.append(xml_field("trg_date_range_type", delay_unit))
        if automation_version == "19.0":
            automation_fields.append(xml_field("trg_date_range_mode", "before" if delay_mode == "before" else "after"))

    if trigger == "on_webhook" and code == "":
        code = "# payload is available in the automation context\n# record is resolved by base.automation.record_getter\nrecord.message_post(body='Webhook automation triggered') if hasattr(record, 'message_post') else None"

    action_fields = [
        xml_field("name", f"{automation_name}: action"),
        f'            <field name="model_id" ref="{escape(model_ref, quote=True)}"/>',
        xml_field("usage", "base_automation"),
        f'            <field name="base_automation_id" ref="{escape(xml_stem, quote=True)}"/>',
        xml_field("state", action_type),
    ]

    if action_type == "code":
        action_fields.append(xml_field("code", code or "# Write safe automation code here\n# Available: env, model, record, records, user, time, datetime, dateutil\npass"))
    elif action_type == "object_write":
        action_fields.append(xml_field("update_path", update_path or "active"))
        if update_boolean_value:
            action_fields.append(xml_field("update_boolean_value", update_boolean_value))
        elif update_value:
            action_fields.append(xml_field("value", update_value))
    elif action_type == "webhook":
        action_fields.append(xml_field("webhook_url", webhook_url or "https://example.com/webhook"))
        if webhook_fields:
            refs = []
            for field in webhook_fields:
                field_ref = field if "." in field else field_external_id(model_name, field, module_name)
                refs.append(f"ref('{field_ref}')")
            action_fields.append(xml_field("webhook_field_ids", f"[(6, 0, [{', '.join(refs)}])]", eval_value=True))
    elif action_type == "object_create":
        action_fields.append(f'            <field name="crud_model_id" ref="{escape(model_ref, quote=True)}"/>')
        action_fields.append(xml_field("value", update_value or automation_name))

    warnings = []
    if trigger == "on_write":
        warnings.append("`on_write` is deprecated; prefer `on_create_or_write` plus `trigger_field_ids`.")
    if trigger == "on_create" and automation_version in {"17.0", "18.0"}:
        warnings.append("`on_create` is deprecated in this version; prefer `on_create_or_write` when possible.")
    if trigger == "on_change" and action_type != "code":
        warnings.append("`on_change` automations can only use `code` actions.")
    if trigger == "on_unlink" and action_type in {"mail_post", "followers", "next_activity"}:
        warnings.append("`on_unlink` cannot use mail, follower, or activity actions because the record is being deleted.")
    if trigger in {"on_message_received", "on_message_sent"}:
        warnings.append("Mail triggers require the target model to inherit `mail.thread`.")
    if trigger in time_triggers and not (date_field or date_field_xml_id) and trigger == "on_time":
        warnings.append("`on_time` requires a date/datetime trigger field; pass `date_field` or `date_field_xml_id`.")
    if trigger == "on_create_or_write" and not trigger_fields:
        warnings.append("No `trigger_fields` were provided; Odoo will consider all stored field updates as possible triggers.")
    if action_type == "object_write" and not update_path:
        warnings.append("`object_write` needs `update_path`; this helper defaulted to `active`.")
    if not model_xml_id and not module_name and not model_name.startswith("x."):
        warnings.append(f"Model XML ID guessed as `{model_ref}`. For dependency models, pass an explicit value such as `project.model_project_task` or `base.model_res_partner`.")

    version_notes = [
        "Odoo 17 uses `tree` in views; Odoo 18+ use `list`.",
        "Odoo 17/18 represent time-based 'before' delays with negative `trg_date_range`.",
        "Odoo 19 uses positive `trg_date_range` plus `trg_date_range_mode` (`before`/`after`).",
        "Creating or editing automations updates registry patches and may affect create/write/unlink/onchange behavior immediately after module update.",
    ]
    security_file = "security/ir.access.csv" if automation_version == "20.0" else "security/ir.model.access.csv"
    if automation_version == "20.0":
        version_notes.insert(1, "Odoo 20 uses `ir.access` access rows with `operation` and `domain`, not older `ir.model.access`/record-rule snippets.")

    xml = f'''<odoo>
    <data noupdate="{data_noupdate}">
        <record id="{escape(xml_stem, quote=True)}" model="base.automation">
{chr(10).join(automation_fields)}
        </record>

        <record id="{escape(action_xml_id, quote=True)}" model="ir.actions.server">
{chr(10).join(action_fields)}
        </record>
    </data>
</odoo>'''

    warning_output = "\n".join(f"- {warning}" for warning in warnings) or "- No blocking warnings from helper inputs. Still test the automation on a disposable database."
    version_output = "\n".join(f"- {note}" for note in version_notes)

    return f"""# Base Automation Helper: {automation_name} (Odoo {automation_version})

**File**: data/{xml_stem}.xml

```xml
{xml}
```

## Manifest Changes

```python
'depends': ['base_automation'],
'data': [
    '{security_file}',
    'data/{xml_stem}.xml',
],
```

## Version-Sensitive Notes

{version_output}

## Guardrails

{warning_output}

## Test Checklist

- Create a record that should trigger the automation and assert the action side effect.
- Create or update a record outside `filter_domain` and assert nothing happens.
- If `trigger_fields` is set, update an unrelated field and assert the action does not run.
- If this automation uses code, test recursion risk when the code writes back to the same model.
- If this automation uses time triggers, run the base automation cron in a test/frozen time scenario.

## References

- Server actions: {get_official_documentation_url(automation_version, 'reference/backend/actions#server-actions-ir-actions-server')}
- Scheduled actions: {get_official_documentation_url(automation_version, 'reference/backend/actions#module-odoo.addons.base.models.ir_cron')}
- Security: {get_official_documentation_url(automation_version, 'reference/backend/security')}
"""
