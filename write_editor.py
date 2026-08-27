import pathlib
src = open('f:/Projects/fastapi_bookings/frontend/src/components/ui/weekly-schedule-editor.tsx.tpl', encoding='utf-8').read()
pathlib.Path('f:/Projects/fastapi_bookings/frontend/src/components/ui/weekly-schedule-editor.tsx').write_text(src, encoding='utf-8')
print('Written', len(src), 'chars')

