import json
from pathlib import Path
p=Path(__file__).with_name('FastAPI-Bookings-Local-Authenticated.postman_collection.json')
c=json.loads(p.read_text(encoding='utf-8'))
def walk(items,path=''):
    for item in items:
        name=str(item.get('name',''))
        current=f'{path}/{name}'
        if 'Hold' in name:
            print(current)
        walk(item.get('item',[]),current)
walk(c.get('item',[]))
