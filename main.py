"""小凌 · 后端启动入口"""
import sys, os, threading

if getattr(sys, 'frozen', False):
    _ROOT = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
else:
    _ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, 'backend'))

import importlib, importlib.machinery
from importlib.abc import MetaPathFinder, Loader

class _AliasLoader(Loader):
    def __init__(self, mod): self._mod = mod
    def create_module(self, spec): return self._mod
    def exec_module(self, module): pass

class _CoreAliasFinder(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname != 'core' and not fullname.startswith('core.'): return None
        try: mod = importlib.import_module('backend.' + fullname)
        except Exception: return None
        return importlib.machinery.ModuleSpec(fullname, _AliasLoader(mod), is_package=hasattr(mod, '__path__'))

try:
    import backend.core
    sys.modules.setdefault('core', sys.modules['backend.core'])
    sys.meta_path.insert(0, _CoreAliasFinder())
except Exception:
    pass

threading.Thread(target=lambda: __import__('backend.rpc.server', fromlist=['serve']).serve(port=50051), daemon=True).start()
import time
while True: time.sleep(3600)
