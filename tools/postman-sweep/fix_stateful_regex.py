from pathlib import Path
p = Path(__file__).with_name('prepare_authenticated_sweep.py')
s = p.read_text(encoding='utf-8')
s = s.replace('r"\\{([A-Za-z_][A-Za-z0-9_]*)\\}"', 'r"(?<!\\{)\\{([A-Za-z_][A-Za-z0-9_]*)\\}(?!\\})"')
p.write_text(s, encoding='utf-8')
print('regex fixed')
