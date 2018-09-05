"""
ckanext-recombinant table management commands

Usage:
  paster recombinant show [DATASET_TYPE [ORG_NAME]] [-c CONFIG]
  paster recombinant create [-f] (-a | DATASET_TYPE ...) [-c CONFIG]
  paster recombinant delete (-a | DATASET_TYPE ...) [-c CONFIG]
  paster recombinant load-csv CSV_FILE ... [-c CONFIG]
  paster recombinant combine (-a | RESOURCE_NAME ...) [-d DIR ] [-c CONFIG]
  paster recombinant target-datasets [-c CONFIG]
  paster recombinant dataset-types [DATASET_TYPE ...] [-c CONFIG]
  paster recombinant remove-broken DATASET_TYPE ... [-c CONFIG]
  paster recombinant update DATASET_TYPE ... [-c CONFIG]
  paster recombinant -h

Options:
  -h --help            Show this screen
  -a --all-types       All dataset types/resource names
  -c --config=CONFIG   CKAN configuration file
  -d --output-dir=DIR  Save CSV files to DIR/RESOURCE_NAME.csv instead
                       of streaming to STDOUT
  -f --force-update    Force update of tables (required for changes
                       to only primary keys/indexes)
"""
import os
import csv
import sys
import logging

from ckan.lib.cli import CkanCommand
from ckan.logic import ValidationError
import paste.script
from ckanapi import LocalCKAN, NotFound
import unicodecsv
import codecs
from docopt import docopt

from ckanext.recombinant.tables import (get_dataset_type_for_resource_name,
    get_dataset_types, get_chromo, get_geno, get_target_datasets,
    get_resource_names)
from ckanext.recombinant.read_csv import csv_data_batch

RECORDS_PER_ORGANIZATION = 1000000 # max records for single datastore query

class TableCommand(CkanCommand):
    summary = __doc__.split('\n')[0]
    usage = __doc__

    # docopt *and* argparse, because we're extending CkanCommand...
    # FIXME: stop extending CkanCommand
    parser = paste.script.command.Command.standard_parser(verbose=True)
    parser.add_option('-a', '--all-types', action='store_true',
        dest='all_types', help='create all registered dataset types')
    parser.add_option('-c', '--config', dest='config',
        default='development.ini', help='Config file to use.')
    parser.add_option('-d', '--output-dir', dest='output_dir')
    parser.add_option('-f', '--force-update', action='store_true',
        dest='force_update', help='force update of tables')

    _orgs = None

    def command(self):
        if '--plugin=ckanext-recombinant' in sys.argv:
            sys.argv.remove('--plugin=ckanext-recombinant')
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
        elif opts['load-csv']:
            return self._load_csv_files(opts['CSV_FILE'])
        elif opts['combine']:
            return self._combine_csv(
                opts['--output-dir'], opts['RESOURCE_NAME'])
        elif opts['target-datasets']:
            return self._target_datasets()
        elif opts['dataset-types']:
            return self._dataset_types(opts['DATASET_TYPE'])
        elif opts['remove-broken']:
            return self._remove_broken(opts['DATASET_TYPE'])
        elif opts['update']:
            return self._update(opts['DATASET_TYPE'])
        else:
            print opts
            return -1

    def _get_orgs(self):
        if not self._orgs:
            lc = LocalCKAN()
            self._orgs = lc.action.organization_list()
        return self._orgs

    def _get_packages(self, dataset_type, orgs, ignore_errors=False):
        lc = LocalCKAN()
        packages = []
        for o in orgs:
            try:
                result = lc.action.recombinant_show(
                    dataset_type=dataset_type,
                    owner_org=o,
                    ignore_errors=ignore_errors)
                packages.append(result)
            except NotFound:
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
            return get_dataset_types()
        return dataset_types

    def _expand_resource_names(self, resource_names):
        if self.options.all_types:
            return get_resource_names()
        return resource_names

    def _create(self, dataset_types):
        """
        Create and update recombinant datasets
        """
        orgs = self._get_orgs()
        lc = LocalCKAN()
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
        lc = LocalCKAN()
        for dtype in self._expand_dataset_types(dataset_types):
            packages = self._get_packages(dtype, orgs, ignore_errors=True)
            for p in packages:
                print 'deleting %s %s' % (dtype, p['owner_org'])
                for r in p['resources']:
                    try:
                        lc.action.datastore_delete(
                            force=True,
                            resource_id=r['id'])
                    except NotFound:
                        pass
                lc.action.package_delete(id=p['id'])

    def _load_csv_files(self, csv_file_names):
        errs = 0
        for n in csv_file_names:
            errs |= self._load_one_csv_file(n)
        return errs

    def _load_one_csv_file(self, name):
        path, csv_name = os.path.split(name)
        assert csv_name.endswith('.csv'), csv_name
        resource_name = csv_name[:-4]
        print resource_name
        chromo = get_chromo(resource_name)
        dataset_type = chromo['dataset_type']
        method = 'upsert' if chromo.get('datastore_primary_key') else 'insert'
        lc = LocalCKAN()

        for org_name, records in csv_data_batch(name, chromo):
            results = lc.action.package_search(
                q='type:%s organization:%s' % (dataset_type, org_name),
                include_private=True,
                rows=2)['results']
            if not results:
                print 'type:%s organization:%s not found!' % (
                    dataset_type, org_name)
                return 1
            if len(results) > 1:
                print 'type:%s organization:%s multiple found!' % (
                    dataset_type, org_name)
                return 1
            for res in results[0]['resources']:
                if res['name'] == resource_name:
                    break
            else:
                print 'type:%s organization:%s missing resource:%s' % (
                    dataset_type, org_name, resource_name)
                return 1

            # convert list values to lists
            list_fields = [f['datastore_id']
                for f in chromo['fields'] if f['datastore_type'] == '_text']
            if list_fields:
                for r in records:
                    for k in list_fields:
                        if not r[k]:
                            r[k] = []
                        else:
                            r[k] = r[k].split(',')

            print '-', org_name, len(records)
            lc.action.datastore_upsert(
                method=method,
                resource_id=res['id'],
                records=records)
        return 0

    def _combine_csv(self, target_dir, resource_names):
        if target_dir and not os.path.isdir(target_dir):
            print '"{0}" is not a directory'.format(target_dir)
            return 1

        orgs = self._get_orgs()
        lc = LocalCKAN()
        outf = sys.stdout
        for resource_name in self._expand_resource_names(resource_names):
            if target_dir:
                outf = open(os.path.join(target_dir,
                    resource_name + '.csv'), 'wb')
            outf.write(codecs.BOM_UTF8)
            self._write_one_csv(
                lc,
                self._get_packages(
                    get_dataset_type_for_resource_name(resource_name), orgs),
                get_chromo(resource_name),
                outf)

            if target_dir:
                outf.close()

    def _write_one_csv(self, lc, pkgs, chromo, outfile):
        out = unicodecsv.writer(outfile)
        column_ids = [f['datastore_id'] for f in chromo['fields']
            ] + chromo.get('csv_org_extras', []) + [
            'owner_org', 'owner_org_title']
        out.writerow(column_ids)

        for pkg in pkgs:
            for res in pkg['resources']:
                if res['name'] == chromo['resource_name']:
                    break
            else:
                print 'resource {0} not found for {1}'.format(
                    chromo['resource_name'], pkg['organization']['name'])
                continue

            try:
                records = lc.action.datastore_search(
                    limit=RECORDS_PER_ORGANIZATION,
                    resource_id=res['id'],
                    )['records']
            except NotFound:
                print 'resource {0} table missing for {1}'.format(
                    chromo['resource_name'], pkg['owner_org'])
                return

            if not records:
                continue

            org_extras = {
                'owner_org': pkg['owner_org'],
                'owner_org_title': pkg['org_title'],
            }
            if chromo.get('csv_org_extras'):
                org = lc.action.organization_show(id=pkg['owner_org'])
                for ename in chromo.get('csv_org_extras', []):
                    org_extras[ename] = u''
                    for e in org['extras']:
                        if e['key'] == ename:
                            org_extras[ename] = e['value']
                            break

            for record in records:
                record.update(org_extras)
                try:
                    row = [unicode(
                        u'' if record[col] is None else
                        u','.join(record[col]) if isinstance(record[col], list) else
                        record[col]
                        ).encode('utf-8') for col in column_ids]
                    out.writerow(['\r\n'.join(col.splitlines()) for col in row])
                except KeyError:
                    print 'resource {0} table missing keys for {1}'.format(
                        chromo['resource_name'], pkg['owner_org'])
                    return

    def _remove_broken(self, target_datasets):
        """
        Low-level command to remove datasets with missing datastore tables
        """
        lc = LocalCKAN()
        for dtype in target_datasets:
            datasets = lc.action.package_search(q="type:%s" % dtype, include_private=True, rows=5000)
            for d in datasets['results']:
                for r in d['resources']:
                    try:
                        lc.action.datastore_search(resource_id=r['id'], rows=1)
                    except NotFound:
                        print 'removing', d['name'], d['title']
                        lc.action.package_delete(id=d['id'])
                        break

    def _update(self, target_datasets):
        """
        Low-level command to update field value in datasets' datastore tables
        """
        lc = LocalCKAN()
        for dtype in target_datasets:
            datasets = lc.action.package_search(q="type:%s" % dtype, include_private=True, rows=5000)
            for d in datasets['results']:
                results = [lc.action.datastore_trigger_each_row(resource_id=r['id'])
                           for r in d['resources']]
                rowcount = sum(results)
                print ' '.join([d['owner_org'], d['organization']['name'],
                               'updated', str(rowcount), 'records'])

    def _target_datasets(self):
        print ' '.join(get_target_datasets())

    def _dataset_types(self, dataset_types):
        for t in self._expand_dataset_types():
            print t + ': ' + ' '.join(
                c['resource_name'] for c in get_geno(t)['resources'])
