import collections
from functools import reduce
import os
import pty
import subprocess

from . import CommandBase, CommandError
from ..ansible_inventory import ansible_get_host_vars
from ..utils import ensure_root, save_term_mode, flatten


class DebootstrapParams(dict):
    def __init__(self, host, host_vars):
        self.host = host
        super().__init__(**host_vars.get('debootstrap', {}))

    @property
    def suite(self):
        try:
            return self['suite']
        except KeyError:
            pass

        with open('/etc/os-release', 'r') as fp:
            suite = next((
                rec[1] for rec in (
                    el.strip().split('=', 1) for el in fp.readlines()
                ) if rec[0] == 'VERSION_CODENAME'
            ), None)
        self['suite'] = suite
        return suite

    @property
    def arch(self):
        try:
            return self['arch']
        except KeyError:
            pass

        arch = subprocess.check_output(('dpkg', '--print-architecture')).decode().strip()
        self['arch'] = arch
        return arch

    @property
    def mirror(self):
        return self.get('mirror')

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(
                f"'{self.__class__.__module__}.{self.__class__.__name__}' "
                f"object has no attribute '{key}'"
            )


class Command(CommandBase):
    PROG = 'ansible-debootstrap'

    silent = False
    dry_run = False

    def create_parser(self, prog=None):
        parser = super().create_parser(prog=prog)
        parser.set_defaults(action=None)
        parser.set_defaults(silent=self.silent)
        parser.set_defaults(dry_run=self.dry_run)

        parser.add_argument(
            'hostpat', action='store',
            metavar='HOST',
            help="ホストを指定する",
        )
        parser.add_argument(
            '--inventory', '-i', action='store',
            help="インベントリを指定する",
            metavar="INVENTORY",
        )
        parser.add_argument(
            '--print-debs', action='store_const',
            dest='action', const='print-debs',
            help="インストールするパッケージ一覧を表示する",
            )
        parser.add_argument(
            '--download-only', action='store_const',
            dest='action', const='download-only',
            help="インストールするパッケージのダウンロードだけを行う",
            )
        parser.add_argument(
            '--unpack-tarball', action='store',
            help="インストールするパッケージを tar アーカイブから取得する",
            )
        parser.add_argument(
            '--make-tarball', action='store',
            help="インストールするパッケージの tar アーカイブを作成する",
            )
        parser.add_argument(
            '--silent', '-s', action='store_true',
            help="コマンド・トレースを表示しない",
            )
        parser.add_argument(
            '--dry-run', '-n', action='store_true',
            help="コマンド・トレースを表示するだけで何も行わない",
        )
        parser.add_argument(
            '--traceback', action='store_true',
            help="traceback on exception",
            )
        parser.add_argument(
            '--version',
            action='version',
            version='%(prog)s version {}'.format(getattr(self, 'VERSION', None) or 'WIP'),
            )
        return parser

    def make_param(self, key, value):
        if value is False:
            return ()

        param = '--{}'.format(key.replace('_', '-'))
        if value is True:
            return (param,)
        if isinstance(value, collections.Iterable) and not isinstance(value, (str, bytes)):
            return (param, ','.join(flatten(value)))
        return (param, value)

    def build_debootstrap_command(self, host, target, params, **options):
        # import pprint
        # pprint.pprint({host: params})

        cmdline = ['debootstrap']
        action = params.get('action')
        if action:
            cmdline.append(f'--{action}')

        cmdparams = (
            self.make_param(key, params[key])
            for key in params.keys()
            if key not in ('action', 'arch', 'suite', 'mirror') and key[0].isalpha()
        )
        cmdline += reduce(lambda acc, el: acc + [el[0], el[1]], cmdparams, [])
        cmdline += ['--arch', params.arch, params.suite, target]

        mirror = params.mirror
        if mirror:
            cmdline.append(mirror)

        return cmdline

    def run_debootstrap(self, host, target, params, **options):
        with save_term_mode():
            cmdline = self.build_debootstrap_command(host, target, params)
            self.write_trace(cmdline)
            if not self.dry_run:
                rc = pty.spawn(cmdline)
                if rc:
                    raise CommandError(f"exec '{cmdline[0]}' failed: exit({rc})")

    def handle(self,
               *args,
               action=None,
               hostpat=None,
               inventory=None,
               silent=False,
               dry_run=False,
               **options):
        self.dry_run = dry_run
        self.silent = not dry_run and silent
        ensure_root()

        for host, host_vars in ansible_get_host_vars(hostpat, inventory):
            # import pprint
            # pprint.pprint({host: host_vars})

            try:
                # debootstrap の target を取得する
                # ; ホスト変数 debootstrap_target または ansible_host の値
                target = os.path.realpath(
                    host_vars.get('debootstrap_target', None) or host_vars['ansible_host'],
                )
            except KeyError:
                raise CommandError(
                    f"no variable definition for host '{host}': "
                    f"'debootstrap_target' nor 'ansible_host'"
                )

            params = DebootstrapParams(host, host_vars)
            if action:
                params['action'] = action

            for name in ('unpack_tarball', 'make_tarball'):
                if options[name]:
                    params[name] = options[name]

            if options.get('make_tarball') or action == 'print-debs':
                target = '{}.debs'.format(target)

            return self.run_debootstrap(host, target, params, **options)
