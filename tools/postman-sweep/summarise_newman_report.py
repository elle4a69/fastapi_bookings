import json, sys
from collections import Counter
from pathlib import Path

p = Path(sys.argv[1])
d = json.loads(p.read_text(encoding='utf-8'))
rows=[]
for e in d.get('run',{}).get('executions',[]):
    code = int(e.get('response',{}).get('code') or 0)
    name = e.get('item',{}).get('name','')
    stream = e.get('response',{}).get('stream')
    if isinstance(stream, list):
        body = bytes(stream).decode('utf-8','replace')
    elif isinstance(stream, dict) and stream.get('type')=='Buffer':
        body = bytes(stream.get('data',[])).decode('utf-8','replace')
    elif isinstance(stream, str):
        body = stream
    else:
        body = ''
    rows.append((code,name,body))
for code,count in sorted(Counter(code for code,_,_ in rows).items()):
    print(f'{code}={count}')
print('---FAILURES---')
for code,name,body in rows:
    if code>=400:
        print(f'{code}\t{name}\t{body[:500].replace(chr(10)," ")}')
