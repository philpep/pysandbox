import os
import types
import signal
import marshal
import resource
import Queue
import multiprocessing

from sandbox import Sandbox, Timeout


class PersistentChild(multiprocessing.Process):

    def __init__(self, config):
        self.config = config
        self.taskq = multiprocessing.Queue()
        self.resultq = multiprocessing.Queue()
        multiprocessing.Process.__init__(self)

    def _run_task(self, task):
        self.taskq.put(task)
        config = task.get("config", self.config)
        try:
            out = self.resultq.get(timeout=config.timeout)
        except Queue.Empty:
            self.terminate()
            raise Timeout()
        else:
            if "error" in out:
                raise out["error"]
            for k in ("locals", "globals"):
                if task.get(k, None) is not None:
                    task[k].clear()
                    task[k].update(out[k])
            return out["result"]

    def call(self, func, args, kw):
        return self._run_task({
            "config": self.config,
            "func": marshal.dumps(func.func_code),
            "name": func.__name__,
            "args": args,
            "kw": kw,
        })

    def execute(self, config, code, globals, locals):
        return self._run_task({
            "config": config,
            "code": code,
            "globals": globals,
            "locals": locals,
        })

    def process_task(self, task):
        try:
            sandbox = Sandbox(task["config"])
            if "code" in task:
                result = sandbox._execute(
                    task["code"], task["globals"], task["locals"])
            else:
                func = types.FunctionType(
                    marshal.loads(task["func"]), globals(), task["name"])
                result = sandbox._call(func, task["args"], task["kw"])
            out = {"result": result}
        except Exception, err:
            out = {"error": err}
        if task.get("globals", None) is not None:
            del task["globals"]["__builtins__"]
            out["globals"] = task["globals"]
        if task.get("locals", None) is not None:
            out["locals"] = task["locals"]
        self.resultq.put(out)

    def run(self):
        # FIXME: multiprocessing.Queue use threading
        #resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
        resource.setrlimit(resource.RLIMIT_AS, (self.config.max_memory, -1))
        # FIXME: stdout/stderr ?
        while True:
            try:
                task = self.taskq.get(timeout=5)
            except Queue.Empty:
                if os.getppid() == 1:
                    # Parent died, suicide myself
                    os.kill(os.getpid(), signal.KILL)
            else:
                self.process_task(task)
