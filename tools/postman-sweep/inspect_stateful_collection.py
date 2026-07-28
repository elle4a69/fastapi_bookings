import json
from pathlib import Path

p = Path(__file__).with_name('FastAPI-Bookings-Local-Authenticated.postman_collection.json')
d = json.loads(p.read_text(encoding='utf-8'))
rows=[]

def walk(items):
    for item in items:
        if 'item' in item:
            walk(item['item'])
        elif 'request' in item:
            url=item['request'].get('url',{})
            raw=url.get('raw','') if isinstance(url,dict) else str(url)
            if '{{' in raw or '/test' in raw or '{test}' in raw:
                rows.append((item.get('name'),raw))
walk(d.get('item',[]))
for name,raw in rows[:100]:
    print(f'{name}: {raw}')
print(f'COUNT={len(rows)}')
