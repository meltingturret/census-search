from click.testing import CliRunner as _ClickRunner

class CliRunner:
    def __init__(self, **kwargs):
        self._runner = _ClickRunner()

    def invoke(self, app, args=None, **kwargs):
        result = self._runner.invoke(app, args or [], catch_exceptions=False, **kwargs)
        return result
