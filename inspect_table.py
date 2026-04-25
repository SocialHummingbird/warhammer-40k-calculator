import importlib.machinery
import importlib.util
from pathlib import Path

loader = importlib.machinery.SourcelessFileLoader('_legacy', 'legacy_main.cpython-312.pyc')
spec = importlib.util.spec_from_loader('_legacy', loader)
legacy = importlib.util.module_from_spec(spec)
loader.exec_module(legacy)

from warhammer.datasheet import load_units_from_csv
units = load_units_from_csv(Path('data/latest'))
attacker = units['infernus squad']
defenders = [units[name] for name in ('cadian command squad', 'boyz', 'intercessor squad')]
table = legacy._build_weapon_table(attacker, defenders, 'all', 'average')
print(table.keys())
print(table['headers'])
print(table['rows'][:2])
