import json
from pathlib import Path

report = json.loads(Path(__file__).with_name('reports').joinpath('latest-full-sweep.json').read_text(encoding='utf-8'))
for execution in report['run']['executions']:
    name = execution.get('item', {}).get('name')
    response = execution.get('response') or {}
    code = response.get('code')
    if name != 'Update Product' and str(code) != '500':
        continue
    request = execution.get('request') or {}
    print('name:', name)
    print('code:', repr(code))
    print('request keys:', request.keys())
    print('request:', request)
    print('response:', response)
    print('assertions:', execution.get('assertions'))
