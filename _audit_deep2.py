import os, sys, importlib, inspect

base = r'G:\AAA研究\02 角色与世界的理解\LuqiAI-Engine-Release'
sys.path.insert(0, base)

deep_check = ['memory', 'motivation', 'game_theory', 'orchestration', 'voice']
for mod_name in deep_check:
    mod_path = 'luqi_engine.' + mod_name
    print('=== %s ===' % mod_name)
    try:
        mod_dir = os.path.join(base, 'luqi_engine', mod_name)
        py_files = [f for f in os.listdir(mod_dir) if f.endswith('.py') and f != '__init__.py']
        print('  .py files: %s' % py_files)

        # Check each .py file for classes
        for pf in py_files:
            sub_path = mod_path + '.' + pf[:-3]
            try:
                sub_mod = importlib.import_module(sub_path)
                for n in dir(sub_mod):
                    if n.startswith('_'): continue
                    obj = getattr(sub_mod, n)
                    if inspect.isclass(obj):
                        mn = getattr(obj, '__module__', '')
                        if mn and sub_path in mn:
                            methods = [m for m in dir(obj) if not m.startswith('_') and callable(getattr(obj, m, None))]
                            print('  [%s] %s (%d methods)' % (pf, n, len(methods)))
            except Exception as e2:
                print('  [%s] import err: %s' % (pf, str(e2)[:40]))
    except Exception as e:
        print('  ERR: %s' % str(e))
    print()
