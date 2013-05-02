from __future__ import with_statement, absolute_import
from .config import SandboxConfig
from .proxy import proxy
from sys import _getframe

def keywordsProxy(keywords):
    # Dont proxy keys because function keywords must be strings
    return dict(
        (key, proxy(value))
        for key, value in keywords.iteritems())

def _call_exec(code, globals, locals):
    exec code in globals, locals

def _dictProxy(data):
    items = data.items()
    data.clear()
    for key, value in items:
        data[proxy(key)] = proxy(value)

class Sandbox(object):
    PROTECTIONS = []

    def __init__(self, config=None):
        if config:
            self.config = config
        else:
            self.config = SandboxConfig()
        self.protections = [protection() for protection in self.PROTECTIONS]
        self.execute_subprocess = None
        self._persistent_child = None
        self.call_fork = None
        # set during enable()
        self.frame = None

    def _call(self, func, args, kw):
        """
        Call a function in the sandbox.
        """
        args = proxy(args)
        kw = keywordsProxy(kw)
        self.frame = _getframe()
        for protection in self.protections:
            protection.enable(self)
        self.frame = None
        try:
            return func(*args, **kw)
        finally:
            for protection in reversed(self.protections):
                protection.disable(self)

    def call(self, func, *args, **kw):
        """
        Call a function in the sandbox.
        """
        if self.config.use_subprocess:
            # FIXME: Only work for simples functions wihtout external code
            if self.config.persistent_child:
                persistent_child = self.get_persitent_child()
                return persistent_child.call(func, args, kw)
            else:
                if self.call_fork is None:
                    from .subprocess_parent import call_fork
                    self.call_fork = call_fork
                return self.call_fork(self, func, args, kw)
        else:
            return self._call(func, args, kw)

    def _execute(self, code, globals, locals):
        """
        Execute the code in the sandbox:

           exec code in globals, locals
        """
        if globals is None:
            globals = {}
        self.frame = _getframe()
        for protection in self.protections:
            protection.enable(self)
        self.frame = None
        try:
            _call_exec(code, globals, locals)
        finally:
            for protection in reversed(self.protections):
                protection.disable(self)

    def execute(self, code, globals=None, locals=None):
        """
        Execute the code in the sandbox:

           exec code in globals, locals

        Run the code in a subprocess except if it is disabled in the sandbox
        configuration.

        The method has no result. By default, use globals={} to get an empty
        namespace.
        """
        if self.config.use_subprocess:
            if self.config.persistent_child:
                persistent_child = self.get_persitent_child()
                return persistent_child.execute(
                    self.config, code, globals, locals)
            else:
                if self.execute_subprocess is None:
                    from .subprocess_parent import execute_subprocess
                    self.execute_subprocess = execute_subprocess
                return self.execute_subprocess(self, code, globals, locals)
        else:
            code = proxy(code)
            if globals is not None:
                _dictProxy(globals)
            if locals is not None:
                _dictProxy(locals)
            return self._execute(code, globals, locals)

    def createCallback(self, func, *args, **kw):
        """
        Create a callback: the function will be called in the sandbox.
        The callback takes no argument.
        """
        args = proxy(args)
        kw = keywordsProxy(kw)
        def callback():
            return self.call(func, *args, **kw)
        return callback

    def get_persitent_child(self):
        if self._persistent_child is not None and \
                not self._persistent_child.is_alive():
            self._persistent_child.join()
            self._persistent_child = None
        if self._persistent_child is None:
            from .persistent_child import PersistentChild
            self._persistent_child = PersistentChild(self.config)
            self._persistent_child.start()
        return self._persistent_child

    def __del__(self):
        if self._persistent_child is not None:
            if self._persistent_child.is_alive():
                self._persistent_child.terminate()
            self._persistent_child.join()
            self._persistent_child = None
