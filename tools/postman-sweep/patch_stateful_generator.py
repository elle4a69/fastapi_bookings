from pathlib import Path

path = Path(__file__).with_name("prepare_authenticated_sweep.py")
text = path.read_text(encoding="utf-8")

insert = '''

STATE_VARIABLES = {
    "service_id": "serviceId",
    "provider_id": "providerId",
    "client_id": "clientId",
    "location_id": "locationId",
    "category_id": "categoryId",
    "resource_id": "resourceId",
    "add_on_id": "addonId",
    "addon_id": "addonId",
    "product_id": "productId",
    "package_id": "packageId",
    "step_id": "packageStepId",
    "workday_id": "workdayId",
    "day_id": "specialDayId",
    "block_id": "blockedTimeId",
    "reserved_id": "reservedTimeId",
    "field_id": "additionalFieldId",
    "promotion_id": "promotionId",
    "tax_rate_id": "taxRateId",
    "webhook_id": "webhookId",
    "note_id": "calendarNoteId",
    "template_id": "notificationTemplateId",
    "rule_id": "reminderRuleId",
    "notification_id": "notificationId",
    "payment_id": "paymentId",
    "booking_id": "bookingId",
    "hold_id": "holdId",
    "series_id": "seriesId",
    "review_id": "reviewId",
    "invoice_id": "invoiceId",
    "config_id": "paymentConfigId",
}

CREATE_CAPTURE_VARIABLES = {
    "Create Service": "serviceId",
    "Create Provider": "providerId",
    "Create Client": "clientId",
    "Create Location": "locationId",
    "Create Category": "categoryId",
    "Create Resource": "resourceId",
    "Create Addon": "addonId",
    "Create Product": "productId",
    "Create Package": "packageId",
    "Add Package Step": "packageStepId",
    "Create Workday": "workdayId",
    "Create Special Day": "specialDayId",
    "Create Blocked Time": "blockedTimeId",
    "Create Reserved Time": "reservedTimeId",
    "Create Additional Field": "additionalFieldId",
    "Create Promotion": "promotionId",
    "Create Tax Rate": "taxRateId",
    "Create Webhook": "webhookId",
    "Create Calendar Note": "calendarNoteId",
    "Create Notification Template": "notificationTemplateId",
    "Create Reminder Rule": "reminderRuleId",
    "Create Notification": "notificationId",
    "Create Payment": "paymentId",
    "Create Booking": "bookingId",
    "Create Public Booking": "bookingId",
    "Create Hold Endpoint": "holdId",
    "Create Series": "seriesId",
    "Submit Review Request": "reviewId",
    "Create Public Invoice": "invoiceId",
}


def add_capture_script(item: dict) -> None:
    variable = CREATE_CAPTURE_VARIABLES.get(str(item.get("name", "")))
    if not variable:
        return
    script = [
        "if (pm.response.code >= 200 && pm.response.code < 300) {",
        "  try {",
        "    const payload = pm.response.json();",
        "    const data = payload && payload.data !== undefined ? payload.data : payload;",
        "    let id = data && data.id;",
        "    if (!id && data) id = data.client_id || data.booking_id || data.hold_id || data.invoice_id;",
        f"    if (id !== undefined && id !== null) pm.environment.set('{variable}', String(id));",
        "  } catch (error) {}",
        "}",
    ]
    item.setdefault("event", []).append({
        "listen": "test",
        "script": {"type": "text/javascript", "exec": script},
    })
'''

marker = '\n\ndef token_values()'
if 'STATE_VARIABLES = {' not in text:
    text = text.replace(marker, insert + marker)

old = '''def replacement_for(name: str, path_values: dict[str, str], method: str) -> str:\n    if name in path_values:\n        return path_values[name]\n    if name.endswith("_id"):\n        return "1" if method == "GET" else "999999"\n    return "test"'''
new = '''def replacement_for(name: str, path_values: dict[str, str], method: str) -> str:\n    variable = STATE_VARIABLES.get(name)\n    if variable:\n        return "{{" + variable + "}}"\n    if name in path_values:\n        return path_values[name]\n    if name.endswith("_id"):\n        return "1"\n    return "test"'''
text = text.replace(old, new)

# Remove the old destructive-method rewrite to 999999.
text = text.replace('''        if method == "DELETE":\n            raw = re.sub(r"/(?:" + "|".join(re.escape(str(v)) for v in set(path_values.values()) if str(v).isdigit()) + r")(?=/|\\?|$)", "/999999", raw)\n''', '')

# Add capture scripts after body normalization.
needle = '        normalise_request_body(request, path_values, str(item.get("name", "request")))\n'
if '        add_capture_script(item)\n' not in text:
    text = text.replace(needle, needle + '        add_capture_script(item)\n')

# Seed lifecycle variables in the environment with discovered IDs.
env_needle = '            {"key": "clientToken", "value": client_token, "enabled": True, "type": "secret"},\n'
if 'for parameter, variable in STATE_VARIABLES.items()' not in text:
    text = text.replace(
        '    environment = {\n',
        '    lifecycle_values = []\n    for parameter, variable in STATE_VARIABLES.items():\n        lifecycle_values.append({"key": variable, "value": str(path_values.get(parameter, "1")), "enabled": True, "type": "default"})\n\n    environment = {\n'
    )
    text = text.replace(env_needle, env_needle + '            *lifecycle_values,\n')

path.write_text(text, encoding="utf-8")
print("Stateful lifecycle patch applied")
