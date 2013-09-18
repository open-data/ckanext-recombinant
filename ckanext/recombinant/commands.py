from ckan.lib.cli import CkanCommand
import ckan.plugins as p

import paste.script

from ckanext.recombinant.plugins import IRecombinant

def _get_tables():
    """
    Find the RecombinantPlugin instance and get the
    table configuration from it
    """
    tables = []
    for plugin in p.PluginImplementations(IRecombinant):
        tables.extend(plugin._tables)
    return tables


class TableCommand(CkanCommand):
    """
    ckanext-recombinant table management commands

    Usage::

        paster table show
                     create [-a | <dataset type> [...]]
                     load-xls <xls file> [...]
    """
    summary = __doc__.split('\n')[0]
    usage = __doc__

    parser = paste.script.command.Command.standard_parser(verbose=True)
    parser.add_option('-a', '--all', action='store_true',
        dest='all', help='create all registered dataset types')
    parser.add_option('-c', '--config', dest='config',
        default='development.ini', help='Config file to use.')


    def command(self):
        cmd = self.args[0]
        self._load_config()

        if cmd == 'show':
            self._show()
        else:
            print self.__doc__

    def _show(self):
        tables = _get_tables()
        print tables
