import pkgutil, importlib
import backend.core as core
fails = []
for finder,name,ispkg in pkgutil.walk_packages(core.__path__, core.__name__+'.'):
    try:
        importlib.import_module(name)
    except Exception as e:
        fails.append((name,e))
print('import failures', fails)
