class Console:
    def print(self, *a, **kw): pass
    def status(self, *a, **kw):
        import contextlib
        return contextlib.nullcontext()
