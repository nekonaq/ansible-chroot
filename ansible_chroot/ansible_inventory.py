from ansible import context
from ansible.cli import CLI
from ansible.cli.inventory import InventoryCLI


class InventoryCLI(InventoryCLI):
    def iter_host_vars(self):
        CLI.run(self)
        self.loader, self.inventory, self.vm = self._play_prereqs()

        for host in self.inventory.get_hosts(context.CLIARGS['host']):
            yield host, self._get_host_variables(host=host)


def ansible_get_host_vars(host, inventory):
    cliargs = ['ansible-inventory']
    if inventory:
        cliargs.extend(['--inventory', inventory])
    cliargs.extend(['--host', host])

    cli = InventoryCLI(cliargs)
    return cli.iter_host_vars()
