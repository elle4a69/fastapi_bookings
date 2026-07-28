from pathlib import Path
p=Path(__file__).with_name('prepare_authenticated_sweep.py')
s=p.read_text(encoding='utf-8')
s=s.replace('normalise_request_body(request, id_values, str(item.get("name", "request")))','normalise_request_body(request, path_values, str(item.get("name", "request")))')
p.write_text(s,encoding='utf-8')
print('fixed')
