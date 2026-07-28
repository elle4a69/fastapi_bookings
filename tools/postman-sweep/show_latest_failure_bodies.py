import json
from pathlib import Path
root=Path(__file__).with_name('reports')
run=sorted([p for p in root.glob('run-*') if (p/'authenticated-sweep.json').exists()])[-1]
r=json.loads((run/'authenticated-sweep.json').read_text(encoding='utf-8'))
for e in r['run']['executions']:
    code=int(e['response']['code'])
    if code>=300:
        stream=e['response'].get('stream')
        if isinstance(stream,list):
            body=bytes(stream).decode('utf-8','replace')
        elif isinstance(stream,dict) and isinstance(stream.get('data'),list):
            body=bytes(stream['data']).decode('utf-8','replace')
        elif isinstance(stream,str):
            body=stream
        else:
            body=''
        print(f"{code}\t{e['item']['name']}\t{body[:500]}")
