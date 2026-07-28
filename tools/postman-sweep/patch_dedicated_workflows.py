from pathlib import Path
p=Path(__file__).with_name('prepare_authenticated_sweep.py')
s=p.read_text(encoding='utf-8')
insert=r'''

def rebuild_remaining_dedicated_workflows(items: list[dict]) -> None:
    """Replace duplicate/order-sensitive operations with one deterministic lifecycle each."""
    # Capture templates before removing originals.
    update_booking = find_request_item(items, "Update Booking")
    create_field = find_request_item(items, "Create Additional Field")
    submit_fields = find_request_item(items, "Submit Public Additional Field Responses")
    submit_review = find_request_item(items, "Submit Review Request")
    resolve_review = find_request_item(items, "Resolve Review Request")
    create_hold = find_request_item(items, "Create Hold Endpoint")
    confirm_hold = find_request_item(items, "Confirm Hold Endpoint")

    remove_request_names(items, {
        "Update Booking",
        "Create Additional Field",
        "Submit Public Additional Field Responses",
        "Submit Review Request",
        "Resolve Review Request",
        "Create Hold Endpoint",
        "Confirm Hold Endpoint",
    })

    workflows=[]
    if update_booking:
        upd=copy.deepcopy(update_booking)
        req=upd.get("request") or {}; body=req.get("body") or {}
        body["raw"]=json.dumps({"notes":"Updated by Postman lifecycle sweep"}, indent=2)
        workflows.append({"name":"Booking Basic Update Workflow","item":[upd]})

    if create_field and submit_fields:
        cf=copy.deepcopy(create_field)
        sf=copy.deepcopy(submit_fields)
        set_json_body(cf, {
            "scope":"booking", "service_id":None,
            "name":f"postman_field_{RUN_SUFFIX}", "label":"Postman Field",
            "field_type":"text", "required":False, "active":True, "position":0,
        })
        add_nested_field_id_script(cf)
        set_json_body(sf, {
            "client_id": int(path_values_global.get("client_id","1")),
            "booking_id": None,
            "responses":[{
                "field_id":"{{additionalFieldId}}",
                "client_id":int(path_values_global.get("client_id","1")),
                "booking_id":None,
                "value":"Postman response"
            }]
        })
        workflows.append({"name":"Additional Field Workflow","item":[cf,sf]})

    if submit_review and resolve_review:
        from datetime import datetime,timedelta,timezone
        sr=copy.deepcopy(submit_review); rr=copy.deepcopy(resolve_review)
        future=datetime.now(timezone.utc).replace(second=0,microsecond=0)+timedelta(days=140,minutes=int(RUN_SUFFIX[:4],16)%600)
        set_json_body(sr,{"preferred_time":future.isoformat().replace("+00:00","Z"),"reason":f"postman-{RUN_SUFFIX}"})
        set_json_body(rr,{"state":"approved","resolution_notes":"Postman sweep approval"})
        workflows.append({"name":"Management Review Workflow","item":[sr,rr]})

    if create_hold and confirm_hold:
        ch=copy.deepcopy(create_hold); hh=copy.deepcopy(confirm_hold)
        # Existing configure step already calculated the best available slot on the template.
        set_json_body(hh,{"hold_id":"{{holdId}}","client_details":None})
        workflows.append({"name":"Hold Confirmation Workflow","item":[ch,hh]})

    items.extend(workflows)
'''
marker='\ndef defer_delete_requests(items: list[dict])'
if 'def rebuild_remaining_dedicated_workflows' not in s:
    s=s.replace(marker,insert+marker)
s=s.replace('    configure_remaining_workflows(collection.get("item", []))\n', '    configure_remaining_workflows(collection.get("item", []))\n    rebuild_remaining_dedicated_workflows(collection.get("item", []))\n')
p.write_text(s,encoding='utf-8')
print('dedicated workflows rebuilt')
