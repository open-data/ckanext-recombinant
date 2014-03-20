from ckan.lib.cli import CkanCommand
from ckan.logic import ValidationError
import paste.script
import ckanapi
import csv
import sys
import logging

from ckanext.recombinant.plugins import _get_tables
from ckanext.recombinant.read_xls import read_xls


class TableCommand(CkanCommand):
    """
    ckanext-recombinant table management commands

    Usage::

        paster recombinant  show
                            create [-a | <dataset type> [...]]
                            destroy [-a | <dataset type> [...]]
                            load-xls <xls file> [...]
                            combine [-a | <dataset type> [...]]

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
        elif cmd == 'load-xls':
            self._load_xls(self.args[1:])
        elif cmd == 'combine':
            self._create_meta_dataset(self.args[1:])
        else:
            print self.__doc__

    def _get_orgs(self):
        if not self._orgs:
            lc = ckanapi.LocalCKAN()
            self._orgs = lc.action.organization_list()
        return self._orgs

    def _get_packages(self, dataset_type):
        lc = ckanapi.LocalCKAN()
        orgs = self._get_orgs()
        packages = lc.action.package_search(
            q="type:%s" % dataset_type,
            rows=1000)['results']
        if len(packages) != len(orgs):
            logging.warn('expected %d packages, received %d' %
                (len(orgs), len(packages)))
        return packages

    def _show(self):
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
            tables = [t for t in _get_tables() if t['dataset_type'] in dts]
        return tables

    def _create(self, dataset_types):
        tables = self._get_tables_from_types(dataset_types)
        if not tables:
            return

        lc = ckanapi.LocalCKAN()
        for t in tables:
            for o in self._get_orgs():
                print t['dataset_type'], o
                dataset = lc.action.package_create(
                    type=t['dataset_type'],
                    title=t['title'],
                    owner_org=o,
                    resources=[{'name':'data'}],
                    )
                lc.action.datastore_create(
                    resource_id=dataset['resources'][0]['id'],
                    fields=[{
                        'id': f['datastore_id'],
                        'type': f['datastore_type'],
                        } for f in t['fields']],
                    primary_key=t['datastore_primary_key'],
                    indexes=t['datastore_indexes'],
                    )


    def _destroy(self, dataset_types):
        tables = self._get_tables_from_types(dataset_types)
        if not tables:
            return

        from ckan.lib.cli import DatasetCmd
        cmd = DatasetCmd('dataset')

        orgs = self._get_orgs()
        lc = ckanapi.LocalCKAN()
        for t in tables:
            for package in self._get_packages(t['dataset_type']):
                for r in package['resources']:
                    try:
                        lc.action.datastore_delete(id=r['id'])
                    except ckanapi.NotFound:
                        pass
                cmd.purge(package['name'])

    def _load_xls(self, xls_file_names):
        for n in xls_file_names:
            self._load_one_xls(n)

    def _load_one_xls(self, n):
        g = read_xls(n)
        sheet_name, org_name = next(g)

        for t in _get_tables():
            if t['xls_sheet_name'] == sheet_name:
                break
        else:
            logging.warn("XLS sheet name '{0}' not found in tables".format(
                sheet_name))
            return

        if org_name not in self._get_orgs():
            logging.warn("Organization name '{0}' not found".format(org_name))
            return

        lc = ckanapi.LocalCKAN()
        org = lc.action.organization_show(id=org_name, include_datsets=False)
        packages = lc.action.package_search(
            q="type:%s AND owner_org:%s" % (t['dataset_type'], org['id']),
            rows=10)['results']
        if len(packages) != 1:
            logging.warn('expected %d packages, received %d' %
                (1, len(packages)))
        p = packages[0]
        resource_id = p['resources'][0]['id']

        records = []
        fields = t['fields']
        for n, row in enumerate(g):
            assert len(row) == len(fields), ("row {0} has {1} columns, "
                "expecting {2}").format(n+3, len(row), len(fields))
            records.append(dict(
                (f['datastore_id'], v) for f, v in zip(fields, row)))

        lc.action.datastore_upsert(resource_id=resource_id, records=records)

    def _create_meta_dataset(self, dataset_types):
        tables = self._get_tables_from_types(dataset_types)
        if not tables:
            return

        lc = ckanapi.LocalCKAN()
        for t in tables:
            out = csv.writer(sys.stdout)
            #output columns header
            columns = [f['label'] for f in t['fields']]
            columns.extend(['Org id', 'Org'])
            out.writerow(columns)

            column_ids = [f['datastore_id'] for f in t['fields']]
            column_ids.extend(['org_name', 'org_title'])

            for package in self._get_packages(t['dataset_type']):
                for res in package['resources']:
                    try:
                        records = lc.action.datastore_search(
                            resource_id=res['id'])['records']
                        self._write_meta_row(records, package, column_ids, out)
                    except ckanapi.NotFound:
                        logging.warn('resource %s not found' % res['id'])

    def _write_meta_row(self, records, package, columns, out):
        for record in records:
            record['org_name'] = package['organization']['name']
            record['org_title'] = package['organization']['title']
            out.writerow([
                unicode(record[col]).encode('utf-8') for col in columns])



