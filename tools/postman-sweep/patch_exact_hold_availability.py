from pathlib import Path
p=Path(__file__).with_name('prepare_authenticated_sweep.py')
s=p.read_text(encoding='utf-8')
s=s.replace('        from app.services.availability_service import get_available_slots', '        from app.services.scheduling_service import compute_availability')
s=s.replace('            from app.models.service import Service\n            service = db.query(Service).filter(Service.id == service_id).first()', '            from app.models.service import Service\n            from app.models.provider import Provider\n            service = db.query(Service).filter(Service.id == service_id).first()\n            provider = db.query(Provider).filter(Provider.id == provider_id).first()')
s=s.replace('                    slots = get_available_slots(db, service.duration, provider_id, probe)\n                    if slots:\n                        start = slots[0]["start"]\n                        end = slots[0]["end"]', '                    day_start = probe.replace(hour=0, minute=0, second=0, microsecond=0)\n                    day_end = day_start + timedelta(days=1)\n                    slots = compute_availability(db, service=service, provider=provider, start_time=day_start, end_time=day_end, desired_duration=service.duration)\n                    if slots:\n                        start = datetime.fromisoformat(slots[0]["start_time"])\n                        end = datetime.fromisoformat(slots[0]["end_time"])')
p.write_text(s,encoding='utf-8')
print('exact hold availability patched')
