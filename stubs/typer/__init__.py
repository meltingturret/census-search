"""Minimal typer stub for testing."""
import sys
import click

def Argument(*args, **kwargs):
    return None

def Option(*args, **kwargs):
    return None

class Exit(SystemExit):
    def __init__(self, code=0):
        super().__init__(code)

class Context:
    def __init__(self, invoked_subcommand=None):
        self.invoked_subcommand = invoked_subcommand
    def get_help(self): return ""
    def exit(self, code=0): raise Exit(code)

def echo(msg="", **kw):
    click.echo(msg, **kw)

class Typer:
    def __init__(self, **kwargs):
        self._commands = {}
        self._callback = None
        self._name = kwargs.get("name", "")
        self._help = kwargs.get("help", "")
        self._no_args_is_help = kwargs.get("no_args_is_help", False)
        self._invoke_without_command = kwargs.get("invoke_without_command", False)
        self._cli = click.Group(name=self._name, help=self._help)

    def command(self, name=None, **kwargs):
        def decorator(fn):
            cmd_name = name or fn.__name__.replace("_", "-")
            self._commands[cmd_name] = fn
            return fn
        return decorator

    def callback(self, **kwargs):
        def decorator(fn):
            self._callback = fn
            return fn
        return decorator

    def __call__(self, *args, **kwargs):
        # Build a real click app for testing
        import click as _click
        @_click.group(name=self._name, help=self._help,
                      invoke_without_command=self._invoke_without_command)
        @_click.pass_context
        def cli(ctx):
            if self._callback:
                ctx2 = Context(invoked_subcommand=ctx.invoked_subcommand)
                ctx2._click_ctx = ctx
                self._callback(ctx2)

        for cmd_name, fn in self._commands.items():
            cli.add_command(_click.command(name=cmd_name)(fn))

        cli(*args, **kwargs)

