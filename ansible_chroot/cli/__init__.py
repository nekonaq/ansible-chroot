import sys
import argparse
import shlex
import subprocess

from .. import __version__


class CommandError(Exception):
    pass


class HelpFormatter(argparse.HelpFormatter):
    def _format_args(self, action, default_metavar):
        if action.metavar == 'COMMAND':
            return '[{}]'.format(action.metavar)
        return super()._format_args(action, default_metavar)


class CommandBase:
    VERSION = __version__
    PROG = None

    @classmethod
    def main(cls):
        try:
            sys.exit(cls().run_from_argv(sys.argv))
        except KeyboardInterrupt:
            sys.exit(1)

    def create_parser(self, prog=None):
        parser = argparse.ArgumentParser(prog=prog or getattr(self, 'PROG', None), formatter_class=HelpFormatter)
        return parser

    def print_usage(self):
        parser = self.create_parser()
        parser.print_usage()

    def run_from_argv(self, argv):
        parser = self.create_parser()
        options = parser.parse_args(argv[1:])
        kwargs = options.__dict__
        args = kwargs.pop('args', [])
        return self.execute(*args, **kwargs)

    def execute(
            self, *args,
            **options):
        self.stdout = options.pop('stdout', sys.stdout)
        self.stderr = options.pop('stderr', sys.stderr)
        self.traceback = options.pop('traceback', False)
        try:
            return self.handle(*args, **options)
        except Exception as err:
            if self.traceback:
                raise
            parser = self.create_parser()
            self.stderr.write("{}: {}\n".format(parser.prog, str(err)))
            sys.exit(1)

    def handle(self, *args, **options):
        raise NotImplementedError(
            f"{self.__class__.__module__}.{self.__class__.__name__}.handle()"
        )

    def write_trace(self, cmdline):
        if self.silent:
            return
        self.stderr.write("+ {}\n".format(' '.join([shlex.quote(el) for el in cmdline])))

    def run_command(self, cmdline):
        self.write_trace(cmdline)
        if self.dry_run:
            return
        rc = subprocess.call(cmdline)
        if rc:
            raise CommandError(f"{cmdline[0]} failed: exit({rc})")
