"""
ckanext-recombinant table management commands

Usage:
  paster recombinant show [DATASET_TYPE [ORG_NAME]] [-c CONFIG]
  paster recombinant create (-a | DATASET_TYPE ...) [-c CONFIG]
  paster recombinant destroy (-a | DATASET_TYPE ...) [-c CONFIG]
  paster recombinant load-xls XLS_FILE ... [-c CONFIG]
  paster recombinant combine (-a | DATASET_TYPE ...) [-c CONFIG]
  paster recombinant target-datasets [-c CONFIG]
  paster recombinant dataset-types [TARGET_DATASET ...] [-c CONFIG]
  paster recombinant -h

Options:
  -h --help           show this screen
  -a --all-types      create all dataset types
  -c --config=CONFIG  CKAN configuration file
"""
from ckan.lib.cli import CkanCommand
from ckan.logic import ValidationError
import paste.script
import ckanapi
import csv
import sys
import logging
import unicodecsv
from docopt import docopt

from ckanext.recombinant.plugins import (
    _get_tables,
    get_target_datasets,
    get_dataset_types)
from ckanext.recombinant.read_xls import read_xls, get_records
from ckanext.recombinant.datatypes import data_store_type

RECORDS_PER_ORGANIZATION = 1000000 # max records for single datastore query

class TableCommand(CkanCommand):
    summary = __doc__.split('\n')[0]
    usage = __doc__

    parser = paste.script.command.Command.standard_parser(verbose=True)
    parser.add_option('-a', '--all-types', action='store_true',
        dest='all_types', help='create all registered dataset types')
    parser.add_option('-c', '--config', dest='config',
        default='development.ini', help='Config file to use.')

    _orgs = None

    def command(self):
        opts = docopt(__doc__)
        self._load_config()

        if opts['show']:
            dataset_type = None
            if opts['DATASET_TYPE']:
                dataset_type = opts['DATASET_TYPE'][0]
            self._show(dataset_type, opts['ORG_NAME'])
        elif opts['create']:
            self._create(opts['DATASET_TYPE'])
        elif opts['destroy']:
            self._destroy(opts['DATASET_TYPE'])
        elif opts['load-xls']:
            self._load_xls(opts['XLS_FILE'])
        elif opts['combine']:
            self._create_meta_dataset(opts['DATASET_TYPE'])
        elif opts['target-datasets']:
            self._target_datasets()
        elif opts['dataset-types']:
            self._dataset_types(opts['TARGET_DATASET'])
        else:
            print opts

    def _get_orgs(self):
        if not self._orgs:
            lc = ckanapi.LocalCKAN()
            self._orgs = lc.action.organization_list()
        return self._orgs

    def _get_packages(self, dataset_type, orgs):
        lc = ckanapi.LocalCKAN()
        packages = []
        for o in orgs:
            result = lc.action.package_search(
                q="type:%s organization:%s" % (dataset_type, o),
            rows=2)['results']
            if result:
                packages.append(result[0])
        return packages

    def _show(self, dataset_type, org_name):
        orgs = self._get_orgs()
        for t in _get_tables():
            if dataset_type and t['dataset_type'] != dataset_type:
                continue
            print u'{t[title]} ({t[dataset_type]})'.format(t=t).encode('utf-8')
            packages =  self._get_packages(t['dataset_type'], orgs)
            if dataset_type:
                for p in packages:
                    if org_name and org_name != p['organization']['name']:
                        continue
                    print p['organization']['name'],
                    print "resource_id =",
                    print p['resources'][0]['id']
            if len(packages) != len(orgs):
                print (' - %d orgs but %d records found' %
                    (len(orgs), len(packages)))
            else:
                print (' - %d records found' % (len(packages),))

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
        orgs = self._get_orgs()
        lc = ckanapi.LocalCKAN()
        for t in tables:
            existing = dict((p['organization']['name'], p)
                for p in self._get_packages(t['dataset_type'], orgs))
            for o in orgs:
                if o in existing:
                    continue
                print t['dataset_type'], o
                dataset = lc.action.package_create(
                    type=t['dataset_type'],
                    title=t['title'],
                    owner_org=o,
                    resources=[{'name':'data', 'url':''}],
                    )
                lc.action.datastore_create(
                    resource_id=dataset['resources'][0]['id'],
                    fields=[{
                        'id': f['datastore_id'],
                        'type':
                            'int' if data_store_type[
                                f['datastore_type']].numeric
                            else 'text',
                        } for f in t['fields']],
                    primary_key=t.get('datastore_primary_key', []),
                    indexes=t.get('datastore_indexes', ""),
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
            for package in self._get_packages(t['dataset_type'], orgs):
                for r in package['resources']:
                    try:
                        lc.action.datastore_delete(id=r['id'])
                    except ckanapi.NotFound:
                        pass
                cmd.purge(package['name'])

    def _load_xls(self, xls_file_names):
        for n in xls_file_names:
            self._load_one_xls(n)

    def _load_one_xls(self, name):
        g = read_xls(name)
        sheet_name, org_name, date_mode = next(g)

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

        if not packages:
            logging.warn(("No recombinant tables for '%s' found. "
                "Try creating them first") % t['dataset_type'])
            return
        p = packages[0]
        resource_id = p['resources'][0]['id']
        records = get_records(g, t['fields'], date_mode)

        print name, len(records)
        lc.action.datastore_upsert(resource_id=resource_id, records=records)

    def _create_meta_dataset(self, dataset_types):
        tables = self._get_tables_from_types(dataset_types)
        if not tables:
            return

        orgs = self._get_orgs()
        lc = ckanapi.LocalCKAN()
        for t in tables:
            out = unicodecsv.writer(sys.stdout)
            # output columns header
            columns = [f['label'] for f in t['fields']]
            columns.extend(['Org id', 'Org'])
            out.writerow(columns)

            column_ids = [f['datastore_id'] for f in t['fields']]
            column_ids.extend(['org_name', 'org_title'])

            for package in self._get_packages(t['dataset_type'], orgs):
                for res in package['resources']:
                    try:
                        records = lc.action.datastore_search(
                            limit=RECORDS_PER_ORGANIZATION,
                            resource_id=res['id'],
                            )['records']
                        self._write_meta_row(records, package, column_ids, out)
                    except ckanapi.NotFound:
                        logging.warn('resource %s not found' % res['id'])

    def _write_meta_row(self, records, package, columns, out):
        try:
            for record in records:
                record['org_name'] = package['organization']['name']
                record['org_title'] = package['organization']['title']
                out.writerow([
                    unicode(record[col]).encode('utf-8') for col in columns])
        except KeyError:
            pass  # don't include data missing any columns

    def _target_datasets(self):
        print ' '.join(get_target_datasets())

    def _dataset_types(self, target_datasets):
        if len(target_datasets) == 0:
            target_datasets = get_target_datasets()
        for target_ds in target_datasets:
            print target_ds + ': ' + ' '.join(get_dataset_types(target_ds))
