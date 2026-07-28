from pathlib import Path

p = Path(__file__).with_name('prepare_authenticated_sweep.py')
s = p.read_text(encoding='utf-8')

if 'from uuid import uuid4' not in s:
    s = s.replace('from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit\n', 'from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit\nfrom uuid import uuid4\n')
if 'RUN_SUFFIX = uuid4().hex[:10]' not in s:
    s = s.replace('TEMP_CLIENT_PASSWORD = "Postman123!"\n', 'TEMP_CLIENT_PASSWORD = "Postman123!"\nRUN_SUFFIX = uuid4().hex[:10]\n')

s = s.replace(
    'f"    if (id !== undefined && id !== null) pm.environment.set(\'{variable}\', String(id));",',
    'f"    if (id !== undefined && id !== null) {{ pm.environment.set(\'{variable}\', String(id)); pm.environment.set(\'{variable}Created\', \'true\'); }}",'
)

insert = '''

DELETE_GUARD_VARIABLES = {
    "Delete Service": "serviceId",
    "Delete Provider": "providerId",
    "Delete Client": "clientId",
    "Delete Location": "locationId",
    "Delete Category": "categoryId",
    "Delete Resource": "resourceId",
    "Delete Addon": "addonId",
    "Delete Product": "productId",
    "Delete Package": "packageId",
    "Delete Package Step": "packageStepId",
    "Delete Workday": "workdayId",
    "Delete Special Day": "specialDayId",
    "Delete Blocked Time": "blockedTimeId",
    "Delete Reserved Time": "reservedTimeId",
    "Delete Additional Field": "additionalFieldId",
    "Delete Promotion": "promotionId",
    "Delete Tax Rate": "taxRateId",
    "Delete Webhook": "webhookId",
    "Delete Calendar Note": "calendarNoteId",
    "Delete Notification Template": "notificationTemplateId",
    "Delete Reminder Rule": "reminderRuleId",
}


def add_delete_guard(item: dict) -> None:
    variable = DELETE_GUARD_VARIABLES.get(str(item.get("name", "")))
    if not variable:
        return
    script = [
        f"if (pm.environment.get('{variable}Created') !== 'true') pm.environment.set('{variable}', '999999');",
    ]
    item.setdefault("event", []).append({
        "listen": "prerequest",
        "script": {"type": "text/javascript", "exec": script},
    })
'''
if 'DELETE_GUARD_VARIABLES = {' not in s:
    s = s.replace('\n\ndef token_values()', insert + '\n\ndef token_values()')

s = s.replace('payload["code"] = "postman-" + slug', 'payload["code"] = "postman-" + slug + "-" + RUN_SUFFIX')
s = s.replace('payload["sku"] = "postman-" + slug', 'payload["sku"] = "postman-" + slug + "-" + RUN_SUFFIX')

# Make generic create emails and logins unique while retaining dedicated client login credentials.
needle = '        if "company" in payload:\n            payload["company"] = TENANT\n'
replacement = '''        if "company" in payload:
            payload["company"] = TENANT
        if request_name not in {"Login Client", "Register Client"}:
            if payload.get("email") == "postman-sweep@example.com":
                payload["email"] = f"postman-{RUN_SUFFIX}@example.com"
            if payload.get("login") in {"test", "<string>"}:
                payload["login"] = f"postman-{RUN_SUFFIX}"
'''
s = s.replace(needle, replacement)

if '        add_delete_guard(item)\n' not in s:
    s = s.replace('        add_capture_script(item)\n', '        add_capture_script(item)\n        add_delete_guard(item)\n')

p.write_text(s, encoding='utf-8')
print('Stateful lifecycle hardened')
