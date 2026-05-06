import os, sys, importlib, inspect

pkg_root = 'luqi_engine'
base = r'G:\AAA研究\02 角色与世界的理解\LuqiAI-Engine-Release'
sys.path.insert(0, base)

print('=' * 70)
print('  COMPREHENSIVE API AUDIT')
print('=' * 70)

modules_info = []
pkg = importlib.import_module(pkg_root)
pkg_dir = os.path.dirname(pkg.__file__)

for item in sorted(os.listdir(pkg_dir)):
    item_path = os.path.join(pkg_dir, item)
    if not os.path.isdir(item_path):
        continue
    if item.startswith('_') or item == '__pycache__':
        continue
    init_file = os.path.join(item_path, '__init__.py')
    if not os.path.exists(init_file):
        continue

    full_name = pkg_root + '.' + item
    try:
        mod = importlib.import_module(full_name)
        symbols = []
        for name in dir(mod):
            if name.startswith('_'):
                continue
            obj = getattr(mod, name, None)
            if obj is None:
                continue
            if inspect.isclass(obj) or inspect.isfunction(obj) or inspect.ismethod(obj):
                mod_name = getattr(obj, '__module__', '')
                if mod_name and mod_name.startswith(pkg_root):
                    kind = 'CLS' if inspect.isclass(obj) else 'FUN'
                    symbols.append(name + '(' + kind + ')')
        py_files = [f for f in os.listdir(item_path) if f.endswith('.py') and f != '__init__.py']
        modules_info.append({'name': item, 'symbols': symbols, 'fc': len(py_files), 'sc': len(symbols)})
    except Exception as e:
        py_files = [f for f in os.listdir(item_path) if f.endswith('.py')]
        modules_info.append({'name': item, 'symbols': [], 'fc': len(py_files), 'sc': 0, 'err': str(e)[:40]})

existing_docs = {'character', 'config', 'core', 'engine', 'interaction', 'llm', 'narrative', 'scene', 'worldview'}

print()
print('--- MODULE INVENTORY ---')
for m in modules_info:
    has_doc = 'YES' if m['name'] in existing_docs else 'NO ***'
    line = m['name'].ljust(20) + str(m['fc']).rjust(4) + 'f  ' + str(m['sc']).rjust(3) + 's  ' + has_doc
    if 'err' in m:
        line += '  [ERR:' + m['err'] + ']'
    print(line)

no_doc = [m['name'] for m in modules_info if m['name'] not in existing_docs]
total_s = sum(m['sc'] for m in modules_info)
doc_count = sum(1 for m in modules_info if m['name'] in existing_docs)

print()
print('Total modules: ' + str(len(modules_info)))
print('With docs: ' + str(doc_count))
print('Missing docs: ' + str(len(no_doc)) + ' -> ' + str(no_doc))
print('Total public symbols: ' + str(total_s))

print()
print('=== DETAILED SYMBOL LIST FOR NO-DOC MODULES ===')
for m in modules_info:
    if m['name'] not in existing_docs and m['sc'] > 0:
        print()
        print('[%s] (%d files, %d symbols):' % (m['name'], m['fc'], m['sc']))
        for s in sorted(m['symbols']):
            print('  - ' + s)
