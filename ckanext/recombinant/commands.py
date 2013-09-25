from ckan.lib.cli import CkanCommand
import ckan.plugins as p
import paste.script
import ckanapi

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
                     destroy [-a | <dataset type> [...]]
                     load-xls <xls file> [...]

    Options::

        -a/--all-types    create all dataset types
    """
    summary = __doc__.split('\n')[0]
    usage = __doc__

    parser = paste.script.command.Command.standard_parser(verbose=True)
    parser.add_option('-a', '--all-types', action='store_true',
        dest='all_types', help='create all registered dataset types')
    parser.add_option('-c', '--config', dest='config',
        default='development.ini', help='Config file to use.')

    _orgs = None

    def command(self):
        cmd = self.args[0]
        self._load_config()

        if cmd == 'show':
            self._show()
        elif cmd == 'create':
            self._create(self.args[1:])
        elif cmd == 'destroy':
            self._destroy(self.args[1:])
        else:
            print self.__doc__

    def _get_orgs(self):
        if not self._orgs:
            lc = ckanapi.LocalCKAN()
            self._orgs = lc.action.organization_list()
        return self._orgs

    def _show(self):
        lc = ckanapi.LocalCKAN()
        for t in _get_tables():
            print '{t[title]} ({t[dataset_type]})'.format(t=t)

            for o in self._get_orgs():
                print ' -', o

    def _get_tables_from_types(self, dataset_types):
        if self.options.all_types:
            if dataset_types:
                print "--all-types makes no sense with dataset types listed"
                return
            tables = _get_tables()
        elif not dataset_types:
            print "please specify dataset types or use -a/--all-types option"
            return
        else:
            dts = set(dataset_types)
            tables = [t for t in _get_tables if t['dataset_type'] in dts]
        return tables

    def _create(self, dataset_types):
        tables = self._get_tables_from_types(dataset_types)
        if not tables:
            return

        lc = ckanapi.LocalCKAN()
        for t in tables:
            for o in self._get_orgs():
                name = '{0}-{1}'.format(t['dataset_type'], o)
                print name
                p = lc.action.package_create(
                    type=t['dataset_type'],
                    name=name,
                    title=t['title'],
                    owner_org=o,
                    resources=[{'url': '_tmp'}],
                    )
                lc.action.datastore_create(
                    resource_id=p['resources'][0]['id'],
                    aliases=name,
                    fields=t['datastore_table']['fields'],
                    primary_key=t['datastore_table']['primary_key'],
                    indexes=t['datastore_table']['indexes'],
                    )


    def _destroy(self, dataset_types):
        tables = self._get_tables_from_types(dataset_types)
        if not tables:
            return

        from ckan.lib.cli import DatasetCmd
        cmd = DatasetCmd('dataset')

        lc = ckanapi.LocalCKAN()
        for t in tables:
            for o in self._get_orgs():
                name = '{0}-{1}'.format(t['dataset_type'], o)
                p = lc.action.package_show(id=name)
                lc.action.datastore_delete(resource_id=p['resources'][0]['id'])
                cmd.purge('{0}-{1}'.format(t['dataset_type'], o))
