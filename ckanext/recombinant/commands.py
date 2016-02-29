"""
ckanext-recombinant table management commands

Usage:
  paster recombinant show [DATASET_TYPE [ORG_NAME]] [-c CONFIG]
  paster recombinant create [-f] (-a | DATASET_TYPE ...) [-c CONFIG]
  paster recombinant delete (-a | DATASET_TYPE ...) [-c CONFIG]
  paster recombinant load-excel EXCEL_FILE ... [-c CONFIG]
  paster recombinant load-csv CSV_FILE ... [-c CONFIG]
  paster recombinant combine DIR (-a | DATASET_TYPE ...) [-c CONFIG]
  paster recombinant target-datasets [-c CONFIG]
  paster recombinant dataset-types [TARGET_DATASET ...] [-c CONFIG]
  paster recombinant -h

Options:
  -h --help           show this screen
  -a --all-types      create all dataset types
  -c --config=CONFIG  CKAN configuration file
  -f --force-update   Force update of tables (required for changes
                      to only primary keys/indexes)
"""
import os
import csv
import sys
import logging

from ckan.lib.cli import CkanCommand
from ckan.logic import ValidationError
import paste.script
import ckanapi
import unicodecsv
from docopt import docopt

from ckanext.recombinant.tables import (
    get_dataset_types, get_geno, get_target_datasets)
from ckanext.recombinant.read_excel import read_excel, get_records

RECORDS_PER_ORGANIZATION = 1000000 # max records for single datastore query
RECORDS_PER_UPSERT = 1000

class TableCommand(CkanCommand):
    summary = __doc__.split('\n')[0]
    usage = __doc__

    parser = paste.script.command.Command.standard_parser(verbose=True)
    parser.add_option('-a', '--all-types', action='store_true',
        dest='all_types', help='create all registered dataset types')
    parser.add_option('-c', '--config', dest='config',
        default='development.ini', help='Config file to use.')
    parser.add_option('-f', '--force-update', action='store_true',
        dest='force_update', help='force update of tables')

    _orgs = None

    def command(self):
        opts = docopt(__doc__)
        self._load_config()

        if opts['show']:
            dataset_type = None
            if opts['DATASET_TYPE']:
                dataset_type = opts['DATASET_TYPE'][0]
            return self._show(dataset_type, opts['ORG_NAME'])
        elif opts['create']:
            return self._create(opts['DATASET_TYPE'])
        elif opts['delete']:
            return self._delete(opts['DATASET_TYPE'])
        elif opts['load-excel']:
            return self._load_excel_files(opts['EXCEL_FILE'])
        elif opts['load-csv']:
            return self._load_csv_files(opts['CSV_FILE'])
        elif opts['combine']:
            return self._combine_csv(opts['DIR'], opts['DATASET_TYPE'])
        elif opts['target-datasets']:
            return self._target_datasets()
        elif opts['dataset-types']:
            return self._dataset_types(opts['TARGET_DATASET'])
        else:
            print opts
            return -1

    def _get_orgs(self):
        if not self._orgs:
            lc = ckanapi.LocalCKAN()
            self._orgs = lc.action.organization_list()
        return self._orgs

    def _get_packages(self, dataset_type, orgs):
        lc = ckanapi.LocalCKAN()
        packages = []
        for o in orgs:
            try:
                result = lc.action.recombinant_show(
                    dataset_type=dataset_type,
                    owner_org=o)
                packages.append(result)
            except ckanapi.NotFound:
                continue
        return packages

    def _show(self, dataset_type, org_name):
        """
        Display some information about the status of recombinant datasets
        """
        orgs = [org_name] if org_name else self._get_orgs()
        types = [dataset_type] if dataset_type else get_dataset_types()

        for dtype in types:
            print u'{geno[title]} ({dtype})'.format(
                geno=get_geno(dtype), dtype=dtype).encode('utf-8')

            packages = self._get_packages(dtype, orgs)
            if dataset_type:
                for p in packages:
                    print p['owner_org']
                    if 'error' in p:
                        print '  *** {p[error]}'.format(p=p)
                    elif not p['metadata_correct']:
                        print '  ! metadata needs to be updated'
                    for r in p['resources']:
                        print ' - id:{r[id]} {r[name]}'.format(r=r),
                        if 'error' in r:
                            print '    *** {r[error]}'.format(r=r)
                        else:
                            print 'rows:{r[datastore_rows]}'.format(r=r)
                            if not r['datastore_correct']:
                                print '   ! datastore needs to be updated'
                            if not r['metadata_correct']:
                                print '   ! metadata needs to be updated'

            if len(packages) != len(orgs):
                print (' > %d orgs but %d records found' %
                    (len(orgs), len(packages)))
            else:
                print (' > %d datasets found' % (len(packages),))
            need_update = sum(1 for p in packages if not p['all_correct'])
            if need_update:
                print (' --> %d need to be updated' % need_update)

    def _expand_dataset_types(self, dataset_types):
        if self.options.all_types:
            if dataset_types:
                print "--all-types makes no sense with dataset types listed"
                return
            return get_dataset_types()
        if not dataset_types:
            print "please specify dataset types or use -a/--all-types option"
            return
        return dataset_types

    def _create(self, dataset_types):
        """
        Create and update recombinant datasets
        """
        orgs = self._get_orgs()
        lc = ckanapi.LocalCKAN()
        for dtype in self._expand_dataset_types(dataset_types):
            packages = self._get_packages(dtype, orgs)
            existing = dict((p['owner_org'], p) for p in packages)
            for o in orgs:
                if o in existing:
                    if existing[o]['all_correct']:
                        if not self.options.force_update:
                            continue
                    print dtype, o, 'updating'
                    lc.action.recombinant_update(
                        owner_org=o, dataset_type=dtype,
                        force_update=self.options.force_update)
                else:
                    print dtype, o
                    lc.action.recombinant_create(owner_org=o, dataset_type=dtype)


    def _delete(self, dataset_types):
        """
        delete recombinant datasets and all their data
        """
        orgs = self._get_orgs()
        lc = ckanapi.LocalCKAN()
        for dtype in self._expand_dataset_types(dataset_types):
            packages = self._get_packages(dtype, orgs)
            for p in packages:
                print 'deleting %s %s' % (dtype, p['owner_org'])
                for r in p['resources']:
                    try:
                        lc.action.datastore_delete(resource_id=r['id'])
                    except NotFound:
                        pass
                lc.action.package_delete(id=p['id'])

    def _load_excel_files(self, excel_file_names):
        for n in excel_file_names:
            self._load_one_excel(n)

    def _load_one_excel_file(self, name):
        g = read_excel(name)
        sheet_name, org_name, date_mode = next(g)

        for t in _get_tables():
            if t['excel_sheet_name'] == sheet_name:
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

    def _load_csv_files(self, csv_file_names):
        for n in csv_file_names:
            self._load_one_csv_file(n)

    def _load_one_csv_file(self, name):
        path, csv_name = os.path.split(name)
        assert csv_name.endswith('.csv'), csv_name
        resource_name = csv_name[:-4]
        print resource_name
        chromo = get_chromo(resource_name)
        expected_columns = [f['datastore_id'] for f in chromo['fields']
            ] + ['owner_org', 'owner_org_title']
        with open(name, 'rb') as infile:
            r = unicodecsv.reader(infile)
            columns_names = r.next()
            if column_names != expected_columns:
                print ("The columns headings sent {0} are different than what "
                "was expected: {1}. ").format(
                ','.join(column_names), ','.join(expected_columns))
                return
            RECORDS_PER_UPSERT

    def _combine_csv(self, target_dir, dataset_types):
        if not os.path.isdir(target_dir):
            print '"{0}" is not a directory'.format(target_dir)
            return 1

        orgs = self._get_orgs()
        lc = ckanapi.LocalCKAN()
        for dtype in self._expand_dataset_types(dataset_types):
            for pkg in self._get_packages(dtype, orgs):
                for chromo in get_geno(dtype)['resources']:
                    self._write_one_csv(lc, pkg, chromo, target_dir)

    def _write_one_csv(self, lc, pkg, chromo, target_dir):
        for res in pkg['resources']:
            if res['name'] == chromo['resource_name']:
                break
        else:
            print 'resource {0} not found for {1}'.format(
                chromo['resource_name'], pkg['organization']['name'])
            return

        with open(os.path.join(
                target_dir, res['name'] + '.csv'), 'wb') as outfile:
            out = unicodecsv.writer(outfile)
            column_ids = [f['datastore_id'] for f in chromo['fields']
                ] + ['owner_org', 'owner_org_title']
            out.writerow(column_ids)

            try:
                records = lc.action.datastore_search(
                    limit=RECORDS_PER_ORGANIZATION,
                    resource_id=res['id'],
                    )['records']
            except ckanapi.NotFound:
                print 'resource {0} table missing for {1}'.format(
                    chromo['resource_name'], pkg['organization']['name'])
                return

            for record in records:
                record['owner_org'] = pkg['organization']['name']
                record['owner_org_title'] = pkg['organization']['title']
                try:
                    out.writerow([
                        unicode(record[col]).encode('utf-8') for col in columns])
                except KeyError:
                    print 'resource {0} table missing keys for {1}'.format(
                        chromo['resource_name'], pkg['organization']['name'])
                    return

    def _target_datasets(self):
        print ' '.join(get_target_datasets())

    def _dataset_types(self, target_datasets):
        if len(target_datasets) == 0:
            target_datasets = get_target_datasets()
        for target_ds in target_datasets:
            print target_ds
