import os
import pty
import stat
import subprocess

from . import CommandBase, CommandError
from ..ansible_inventory import ansible_get_host_vars
from ..utils import ensure_root, save_term_mode


class Command(CommandBase):
    PROG = 'ansible-chroot'

    silent = False
    dry_run = False

    def create_parser(self, prog=None):
        parser = super().create_parser(prog=prog)
        parser.set_defaults(action='chroot')
        parser.set_defaults(local=False)
        parser.set_defaults(silent=self.silent)
        parser.set_defaults(dry_run=self.dry_run)

        parser.add_argument(
            'hostpat', action='store',
            metavar='HOST',
            help="ホストを指定する",
        )
        parser.add_argument(
            'args', action='store', nargs='...',
            metavar='COMMAND',
            help="実行するコマンド",
        )
        parser.add_argument(
            '--inventory', '-i', action='store',
            help="インベントリを指定する",
            metavar="INVENTORY",
        )
        parser.add_argument(
            '--target-suffix', '-S', action='store',
            help="ターゲットのサフィックスを指定する",
            metavar="SUFFIX",
        )
        parser.add_argument(
            '--overlay', action='store',
            help="オーバーレイマウントを行う",
            )
        parser.add_argument(
            '--local', '-l', action='store_true',
            help="コマンドをローカルで実行する",
            )
        parser.add_argument(
            '--print-target', action='store_true',
            help="chroot ディレクトリを表示する",
            )
        parser.add_argument(
            '--mount', '-m', action='store_const',
            dest='action', const='mount',
            help="chroot 環境に必要なファイルシステムをマウントする",
            )
        parser.add_argument(
            '--mount-overlay-rw', action='store_const',
            dest='action', const='mount-overlay-rw',
            help="オーバーレイマウントの上位レイヤだけをマウントする",
            )
        parser.add_argument(
            '--umount', '-u', action='store_const',
            dest='action', const='umount',
            help="chroot 環境に必要なファイルシステムをアンマウントする",
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

    mount_point_list = (
        '/sys',
        '/proc',
        '/dev',
        '/dev/pts',
    )

    def action__mount(self, host, target, args, overlay=None, **options):
        if overlay:
            ovupper = '.'.join([target, 'overlay/upper'])
            ovwork = '.'.join([target, 'overlay/work'])

            for mp in (target, ovupper, ovwork):
                if not os.path.exists(mp):
                    self.run_command(('mkdir', '-p', mp))

            # target を ovlower として使う
            ovlower = target
            if overlay is not True:
                if stat.S_ISDIR(os.stat(overlay).st_mode):
                    # overlay を target にマウントしてから ovlower として使う
                    self.run_command(('mount', '--bind', overlay, target))
                else:
                    # overlay を target にマウントしてから ovlower として使う
                    self.run_command(('mount', overlay, target))

            self.run_command((
                'mount', '-t', 'overlay', '-o',
                f'lowerdir={ovlower},upperdir={ovupper},workdir={ovwork}',
                'overlay',
                target,
            ))

        for mp in self.mount_point_list:
            self.run_command(('mount', '--bind', mp, ''.join([target, mp])))

    def action__mount_overlay_rw(self, host, target, args, overlay=None, **options):
        ovupper = '.'.join([target, 'overlay/upper'])
        ovwork = '.'.join([target, 'overlay/work'])
        ovempty = '.'.join([target, 'overlay/empty'])

        for mp in (target, ovupper, ovwork, ovempty):
            if not os.path.exists(mp):
                self.run_command(('mkdir', '-p', mp))

        # ovempty を ovlower として使う
        ovlower = ovempty
        self.run_command((
            'mount', '-t', 'overlay', '-o',
            f'lowerdir={ovlower},upperdir={ovupper},workdir={ovwork}',
            'overlay',
            target,
        ))


    def iter_mount_point(self, host, target):
        output = subprocess.check_output(('mount',))
        for line in output.decode().splitlines():
            row = line.split()
            if not row[2].startswith(target):
                continue
            yield row[2]

    def action__umount(self, host, target, args, **options):
        for mount_point in sorted(list(self.iter_mount_point(host, target)), reverse=True):
            self.run_command(('umount', mount_point))

    def action__chroot(self, host, target, args, vars={}, overlay=None, local=False, **options):
        cmdargs = tuple((
            el.format(
                host,
                inventory_hostname=host,
                chroot_target=target,
                **vars
            ) for el in args
        ))

        if not os.path.exists(target):
            self.run_command(('mkdir', '-p', target))

        with save_term_mode():
            try:
                self.action__mount(host, target, args, overlay=overlay)
                if local:
                    cmdline = cmdargs or ('/bin/bash',)
                else:
                    cmdline = (
                        '/usr/bin/env',
                        'LANG=C.UTF-8',
                        'HOME=/',
                        '/usr/sbin/chroot', target,
                    ) + cmdargs

                self.write_trace(cmdline)
                if not self.dry_run:
                    rc = pty.spawn(cmdline)
                    if rc:
                        raise CommandError(f"exec '{cmdline[0]}' failed: exit({rc})")
            finally:
                self.action__umount(host, target, args)

    actions = {
        'chroot': action__chroot,
        'mount': action__mount,
        'mount-overlay-rw': action__mount_overlay_rw,
        'umount': action__umount,
    }

    def handle(self,
               *args,
               action=None,
               hostpat=None,
               inventory=None,
               target_suffix=None,
               overlay=None,
               print_target=None,
               silent=False,
               dry_run=False,
               **options):
        overlay = overlay if overlay else overlay == ''
        self.dry_run = dry_run
        self.silent = not dry_run and silent

        if not print_target:
            ensure_root()

        for host, host_vars in ansible_get_host_vars(hostpat, inventory):
            # import pprint
            # pprint.pprint({host: host_vars})
            try:
                target = os.path.realpath(host_vars['ansible_host'])  # chroot target
            except KeyError:
                raise CommandError(
                    f"no variable definition for host '{host}': 'ansible_host'",
                )

            target += target_suffix if target_suffix else ''
            if print_target:
                self.stdout.write(f"{host}\t{target}\n")
                continue

            overlay = overlay or host_vars.get('chroot_overlay')
            try:
                action_method = self.actions[action]
            except KeyError:
                raise CommandError(
                    f"unknown action: {action}",
                )

            return action_method(
                self, host, target, args=args, vars=host_vars, overlay=overlay, **options
            )
