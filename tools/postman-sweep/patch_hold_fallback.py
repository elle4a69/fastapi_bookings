from pathlib import Path
p=Path(__file__).with_name('prepare_authenticated_sweep.py')
s=p.read_text(encoding='utf-8')
old='''            "provider_id": int(path_values_global.get("provider_id", "1")),
            "location_id": int(path_values_global.get("location_id", "1")),
            "client_id": int(path_values_global.get("client_id", "1")),'''
new='''            "provider_id": None,
            "location_id": None,
            "client_id": int(path_values_global.get("client_id", "1")),'''
s=s.replace(old,new)
p.write_text(s,encoding='utf-8')
print('hold provider fallback patched')
