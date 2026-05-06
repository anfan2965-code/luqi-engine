import os, sys, importlib, inspect, re

base = r'G:\AAA研究\02 角色与世界的理解\LuqiAI-Engine-Release'
sys.path.insert(0, base)

print('=' * 70)
print('  DEEP DOC-vs-CODE AUDIT')
print('=' * 70)

def get_all_classes(module_path):
    try:
        mod = importlib.import_module(module_path)
        classes = []
        for name in dir(mod):
            if name.startswith('_'):
                continue
            obj = getattr(mod, name)
            if inspect.isclass(obj):
                mod_name = getattr(obj, '__module__', '')
                if mod_name and module_path in mod_name:
                    methods = [m for m in dir(obj) if not m.startswith('_') and callable(getattr(obj, m, None))]
                    classes.append((name, len(methods)))
        return classes
    except Exception as e:
        return [('ERROR:' + str(e)[:30], 0)]

def read_doc_symbols(doc_path):
    fpath = os.path.join(base, 'docs', 'api', doc_path + '.md')
    if not os.path.exists(fpath):
        return []
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()
    # Find class references like `ClassName` or **ClassName**
    pattern = r'(?:^|\s)(?:class\s+|`|\*\*)([A-Z][A-Za-z_0-9]+)(?:`|\*\*|\()'
    found = set(re.findall(pattern, content))
    return list(found)

# All modules to audit
all_modules = {
    'agents': 'luqi_engine.agents',
    'character': 'luqi_engine.character',
    'config': 'luqi_engine.core.config',
    'core': 'luqi_engine.core',
    'engine': 'luqi_engine.engine',
    'game_theory': 'luqi_engine.game_theory',
    'interaction': 'luqi_engine.interaction',
    'llm': 'luqi_engine.llm',
    'local_model': 'luqi_engine.local_model',
    'memory': 'luqi_engine.memory',
    'motivation': 'luqi_engine.motivation',
    'narrative': 'luqi_engine.narrative',
    'orchestration': 'luqi_engine.orchestration',
    'performance': 'luqi_engine.performance',
    'scheduler': 'luqi_engine.scheduler',
    'scene': 'luqi_engine.scene',
    'training': 'luqi_engine.training',
    'voice': 'luqi_engine.voice',
    'worldview': 'luqi_engine.worldview',
}

docs_exist = {'character', 'config', 'core', 'engine', 'interaction', 'llm', 'narrative', 'scene', 'worldview'}

print()
print('%-18s %6s %6s  %-40s' % ('Module', 'Code', 'Doc', 'Status'))
print('-' * 75)

total_code = 0
total_doc = 0
gaps = []

for mod_name, import_path in sorted(all_modules.items()):
    code_classes = get_all_classes(import_path)
    code_names = set(c[0] for c in code_classes)
    total_code += len(code_classes)

    if mod_name in docs_exist:
        doc_syms = read_doc_symbols(mod_name)
        total_doc += len(doc_syms)

        missing_in_doc = code_names - set(doc_syms)
        extra_in_doc = set(doc_syms) - code_names

        if missing_in_doc or extra_in_doc:
            status = 'MISMATCH'
            gaps.append((mod_name, sorted(missing_in_doc), sorted(extra_in_doc), len(code_classes), len(doc_syms)))
        else:
            status = 'OK'
        print('%-18s %6d %6d  %-40s' % (mod_name, len(code_classes), len(doc_syms), status))
    else:
        status = 'NO DOC ***'
        print('%-18s %6d %6s  %-40s' % (mod_name, len(code_classes), '-', status))
        gaps.append((mod_name, sorted(code_names), [], len(code_classes), 0))

print()
print('Total code classes: %d' % total_code)
print('Total doc entries:  %d' % total_doc)
print()

if gaps:
    print('=' * 70)
    print('  GAPS DETECTED')
    print('=' * 70)
    for mod_name, missing, extra, nc, nd in gaps:
        print()
        print('[%s] code=%d doc=%d' % (mod_name, nc, nd))
        if missing:
            print('  IN CODE BUT NOT IN DOC (%d):' % len(missing))
            for m in missing[:15]:
                print('    + ' + m)
            if len(missing) > 15:
                print('    ... and %d more' % (len(missing) - 15))
        if extra:
            print('  IN DOC BUT NOT IN CODE (%d):' % len(extra))
            for e in extra[:10]:
                print('    ? ' + e)
