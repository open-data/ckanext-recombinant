import click
import os
import csv
import sys
import json

from ckan.logic import ValidationError
from ckanapi import LocalCKAN, NotFound

from ckanext.recombinant.tables import (get_dataset_type_for_resource_name,
    get_dataset_types, get_chromo, get_geno, get_target_datasets,
    get_resource_names)
from ckanext.recombinant.read_csv import csv_data_batch
from ckanext.recombinant.write_excel import excel_template
from ckanext.recombinant.logic import _update_triggers


DATASTORE_PAGINATE = 10000 # max records for single datastore query


def get_commands():
    return recombinant


@click.group(short_help="Recombinant table management commands")
def recombinant():
    """Recombinant table management commands.
    """
    pass


@recombinant.command(short_help="Display some information about the status of recombinant datasets.")
@click.argument("dataset_type", required=False)
@click.argument("org_name", required=False)
@click.option('-v', '--verbose', is_flag=True, type=click.BOOL, help='Increase verbosity.')
def show(dataset_type=None, org_name=None, verbose=False):
    """
    Display some information about the status of recombinant datasets

    Full Usage:\n
        recombinant show [DATASET_TYPE [ORG_NAME]]
    """
    _show(dataset_type, org_name, verbose=verbose)


@recombinant.command(short_help="Create and update triggers.")
@click.argument("dataset_type", required=False, nargs=-1)
@click.option(
    "-a",
    "--all-types",
    is_flag=True,
    help="All dataset types/resource names",
)
@click.option('-v', '--verbose', is_flag=True, type=click.BOOL, help='Increase verbosity.')
def create_triggers(dataset_type=None, all_types=False, verbose=False):
    """
    Create and update triggers

    Full Usage:\n
        recombinant create-triggers (-a | DATASET_TYPE ...)
    """
    _create_triggers(dataset_type, all_types, verbose=verbose)


@recombinant.command(short_help="Delete datastore tables and packages for empty recombinant resources.")
@click.argument("dataset_type", required=False, nargs=-1)
@click.option(
    "-a",
    "--all-types",
    is_flag=True,
    help="All dataset types/resource names",
)
@click.option('-v', '--verbose', is_flag=True, type=click.BOOL, help='Increase verbosity.')
def remove_empty(dataset_type=None, all_types=False, verbose=False):
    """
    Delete datastore tables and packages for empty recombinant resources

    Full Usage:\n
        recombinant remove-empty (-a | DATASET_TYPE ...)
    """
    _remove_empty(dataset_type, all_types, verbose=verbose)


@recombinant.command(short_help="Triggers recombinant update for recombinant resources.")
@click.argument("dataset_type", required=False, nargs=-1)
@click.option(
    "-a",
    "--all-types",
    is_flag=True,
    help="All dataset types/resource names",
)
@click.option(
    "-f",
    "--force-update",
    is_flag=True,
    help="Force update of tables (required for changes to only primary keys/indexes)",
)
@click.option('-v', '--verbose', is_flag=True, type=click.BOOL, help='Increase verbosity.')
def update(dataset_type=None, all_types=False, force_update=False, verbose=False):
    """
    Triggers recombinant update for recombinant resources

    Full Usage:\n
        recombinant update (-a | DATASET_TYPE ...) [-f]
    """
    _update(dataset_type, all_types, force_update, verbose=verbose)


@recombinant.command(short_help="Delete recombinant datasets and all their data.")
@click.argument("dataset_type", required=False, nargs=-1)
@click.option(
    "-a",
    "--all-types",
    is_flag=True,
    help="All dataset types/resource names",
)
@click.option('-v', '--verbose', is_flag=True, type=click.BOOL, help='Increase verbosity.')
def delete(dataset_type=None, all_types=False, verbose=False):
    """
    Delete recombinant datasets and all their data

    Full Usage:\n
        recombinant delete (-a | DATASET_TYPE ...)
    """
    _delete(dataset_type, all_types, verbose=verbose)


@recombinant.command(short_help="Load CSV file(s) rows into recombinant resources datastore.")
@click.argument("csv_file", type=click.File('r'), nargs=-1)
@click.option('-v', '--verbose', is_flag=True, type=click.BOOL, help='Increase verbosity.')
def load_csv(csv_file, verbose=False):
    """
    Load CSV file(s) rows into recombinant resources datastore

    Full Usage:\n
        recombinant load-csv CSV_FILE ...
    """
    _load_csv_files(csv_file, verbose=verbose)


@recombinant.command(short_help="Output all datastore data to CSV for given resource names.")
@click.argument("resource_name", required=False, nargs=-1)
@click.option(
    "-a",
    "--all-types",
    is_flag=True,
    help="All dataset types/resource names",
)
@click.option(
    "-d",
    "--output-dir",
    default=None,
    required=True,
    help="Save CSV files to DIR/RESOURCE_NAME.csv instead of streaming to STDOUT",
)
@click.option('-v', '--verbose', is_flag=True, type=click.BOOL, help='Increase verbosity.')
def combine(resource_name, all_types=False, output_dir=None, verbose=False):
    """
    Output all datastore data to CSV for given resource names

    Full Usage:\n
        recombinant combine (-a | RESOURCE_NAME ...) [-d DIR ]
    """
    _combine_csv(output_dir, resource_name, all_types, verbose=verbose)


@recombinant.command(short_help="Output configured target datasets.")
@click.option('-v', '--verbose', is_flag=True, type=click.BOOL, help='Increase verbosity.')
def target_datasets(verbose=False):
    """
    Find the RecombinantPlugin instance and output its
    configured target datasets (e.g., ['ati', 'pd', ...])

    Full Usage:\n
        recombinant target-datasets
    """
    _target_datasets(verbose=verbose)


@recombinant.command(short_help="Output dataset types of recombinant resources.")
@click.argument("dataset_type", required=False, nargs=-1)
@click.option('-v', '--verbose', is_flag=True, type=click.BOOL, help='Increase verbosity.')
def dataset_types(dataset_type=None, verbose=False):
    """
    Output dataset types of recombinant resources

    Full Usage:\n
        recombinant dataset-types [DATASET_TYPE ...]
    """
    _dataset_types(dataset_type, verbose=verbose)


@recombinant.command(short_help="Low-level command to remove datasets with missing datastore tables.")
@click.argument("dataset_type", nargs=-1)
@click.option('-v', '--verbose', is_flag=True, type=click.BOOL, help='Increase verbosity.')
def remove_broken(dataset_type, verbose=False):
    """
    Low-level command to remove datasets with missing datastore tables

    Full Usage:\n
        recombinant remove-broken DATASET_TYPE ...
    """
    _remove_broken(dataset_type, verbose=verbose)


@recombinant.command(short_help="Low-level command to run triggers on datasets' datastore tables.")
@click.argument("dataset_type", nargs=-1)
@click.option("-a", "--all-types", is_flag=True, type=click.BOOL, help="All dataset types/resource names")
@click.option('-v', '--verbose', is_flag=True, type=click.BOOL, help='Increase verbosity.')
def run_triggers(dataset_type, all_types=False, verbose=False):
    """
    Low-level command to run triggers on datasets' datastore tables

    Full Usage:\n
        recombinant run-triggers DATASET_TYPE ...
    """
    _run_triggers(dataset_type, all_types=all_types, verbose=verbose)


@recombinant.command(short_help="Output the recombinant excel template to a file path.")
@click.argument("dataset_type")
@click.argument("org_name")
@click.argument("output_file")
@click.option('-v', '--verbose', is_flag=True, type=click.BOOL, help='Increase verbosity.')
def template(dataset_type, org_name, output_file, verbose=False):
    """
    Output the recombinant excel template to a file path

    Full Usage:\n
        recombinant DATASET_TYPE ORG_NAME OUTPUT_FILE
    """
    _template(dataset_type, org_name, output_file, verbose=verbose)


def _get_orgs():
    lc = LocalCKAN()
    return lc.action.organization_list()


def _get_packages(dataset_type, orgs, ignore_errors=False):
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


def _show(dataset_type, org_name, verbose=False):
    """
    Display some information about the status of recombinant datasets
    """
    orgs = [org_name] if org_name else _get_orgs()
    types = [dataset_type] if dataset_type else get_dataset_types()

    for dtype in types:
        click.echo(u'{geno[title]} ({dtype})'.format(
            geno=get_geno(dtype), dtype=dtype).encode('utf-8'))

        packages = _get_packages(dtype, orgs)
        if dataset_type:
            for p in packages:
                click.echo(p['owner_org'])
                if 'error' in p:
                    click.echo('  *** {p[error]}'.format(p=p))
                elif not p['metadata_correct']:
                    click.echo('  ! metadata needs to be updated')
                for r in p['resources']:
                    click.echo(' - id:{r[id]} {r[name]}'.format(r=r))
                    if 'error' in r:
                        click.echo('    *** {r[error]}'.format(r=r))
                    else:
                        click.echo('rows:{r[datastore_rows]}'.format(r=r))
                        if not r['datastore_correct']:
                            click.echo('   ! datastore needs to be updated')
                        if not r['metadata_correct']:
                            click.echo('   ! metadata needs to be updated')

        click.echo(' > %d orgs with %d records found' %
            (len(orgs), len(packages)))
        need_update = sum(1 for p in packages if not p['all_correct'])
        if need_update:
            click.echo(' --> %d need to be updated' % need_update)


def _update(dataset_types, all_types=False, force_update=False, verbose=False):
    """
    Triggers recombinant update for recombinant resources
    """
    orgs = _get_orgs()
    lc = LocalCKAN()
    for dtype in _expand_dataset_types(dataset_types, all_types):
        packages = _get_packages(dtype, orgs)
        existing = dict((p['owner_org'], p) for p in packages)
        for o in orgs:
            if o in existing:
                if existing[o]['all_correct']:
                    if not force_update:
                        continue
                click.echo('%s %s updating' % (dtype, o))
                lc.action.recombinant_update(
                    owner_org=o, dataset_type=dtype,
                    force_update=force_update)


def _expand_dataset_types(dataset_types, all_types=False):
    if all_types:
        return get_dataset_types()
    if isinstance(dataset_types, str):
        return [dataset_types]
    return dataset_types


def _expand_resource_names(resource_names, all_types=False):
    if all_types:
        return get_resource_names()
    if isinstance(resource_names, str):
        return [resource_names]
    return resource_names


def _create_triggers(dataset_types, all_types=False, verbose=False):
    """
    Create and update triggers
    """
    lc = LocalCKAN()
    for dtype in _expand_dataset_types(dataset_types, all_types):
        for chromo in get_geno(dtype)['resources']:
            _update_triggers(lc, chromo)


def _remove_empty(dataset_types, all_types=False, verbose=False):
    """
    Delete datastore tables and packages for empty recombinant resources
    """
    orgs = _get_orgs()
    lc = LocalCKAN()
    for dtype in _expand_dataset_types(dataset_types, all_types):
        packages = _get_packages(dtype, orgs)
        for p in packages:
            if not any(r['datastore_rows'] for r in p['resources']):
                click.echo('deleting %s %s' % (dtype, p['owner_org']))
                for r in p['resources']:
                    try:
                        lc.action.datastore_delete(
                            force=True,
                            resource_id=r['id'])
                    except NotFound:
                        pass
                lc.action.package_delete(id=p['id'])


def _delete(dataset_types, all_types=False, verbose=False):
    """
    Delete recombinant datasets and all their data
    """
    orgs = _get_orgs()
    lc = LocalCKAN()
    for dtype in _expand_dataset_types(dataset_types, all_types):
        packages = _get_packages(dtype, orgs, ignore_errors=True)
        for p in packages:
            click.echo('deleting %s %s' % (dtype, p['owner_org']))
            for r in p['resources']:
                try:
                    lc.action.datastore_delete(
                        force=True,
                        resource_id=r['id'])
                except NotFound:
                    pass
                except ValidationError as e:
                    click.echo('failed %s %s -- %s' % (dtype, p['owner_org'], str(e.error_dict)), err=True)
            lc.action.package_delete(id=p['id'])


def _load_csv_files(csv_file_names, verbose=False):
    """
    Load CSV file(s) rows into recombinant resources datastore
    """
    errs = 0
    for n in csv_file_names:
        # pass click.File prop
        errs |= _load_one_csv_file(n.name)
    return errs


def _load_one_csv_file(name):
    """
    Load CSV file rows into recombinant resources datastore
    """
    path, csv_name = os.path.split(name)
    assert csv_name.endswith('.csv'), csv_name
    resource_name = csv_name[:-4]
    click.echo(resource_name)
    chromo = get_chromo(resource_name)

    dataset_type = chromo['dataset_type']
    method = 'upsert' if chromo.get('datastore_primary_key') else 'insert'
    lc = LocalCKAN()
    errors = 0

    for org_name, records in csv_data_batch(name, chromo):
        results = lc.action.package_search(
            q='type:%s AND organization:%s' % (dataset_type, org_name),
            include_private=True,
            rows=2)['results']

        if not results:
            lc.action.recombinant_create(dataset_type=dataset_type, owner_org=org_name)
            results = lc.action.package_search(
                q='type:%s AND organization:%s' % (dataset_type, org_name),
                include_private=True,
                rows=2)['results']

        if len(results) > 1:
            click.echo('type:%s organization:%s multiple found!' % (
                dataset_type, org_name))
            return 1

        for res in results[0]['resources']:
            if res['name'] == resource_name:
                break
        else:
            click.echo('type:%s organization:%s missing resource:%s' % (
                dataset_type, org_name, resource_name))
            return 1

        # convert list values to lists
        list_fields = [f['datastore_id']
            for f in chromo['fields'] if f['datastore_type'] == '_text' and not f.get('published_resource_computed_field')]
        if list_fields:
            for r in records:
                for k in list_fields:
                    if not r[k]:
                        r[k] = []
                    else:
                        r[k] = r[k].split(',')

        click.echo('- %s %s' % (org_name, len(records)))

        if 'csv_org_extras' in chromo:
            # remove 'csv_org_extras' fields from records
            for r in records:
                for e in chromo['csv_org_extras']:
                    del r[e]

        offset = 0
        while offset < len(records):
            try:
                lc.action.datastore_upsert(
                    method=method,
                    resource_id=res['id'],
                    records=records[offset:])
            except ValidationError as err:
                if 'records_row' not in err.error_dict:
                    raise
                bad = err.error_dict['records_row']
                errors |= 2
                sys.stderr.write(json.dumps([
                    err.error_dict['records'],
                    org_name,
                    records[offset + bad]]).encode('utf-8') + '\n')
                # retry records that passed validation
                good = records[offset: offset+bad]
                if good:
                    lc.action.datastore_upsert(
                        method=method,
                        resource_id=res['id'],
                        records=good)
                offset += bad + 1  # skip and continue
            else:
                break
    return errors


def _combine_csv(target_dir, resource_names, all_types=False, verbose=False):
    """
    Output all datastore data to CSV for given resource names
    """
    if not os.path.isdir(target_dir):
        click.echo('"{0}" is not a directory'.format(target_dir))
        return 1

    orgs = _get_orgs()
    lc = LocalCKAN()
    for resource_name in _expand_resource_names(resource_names, all_types):
        if verbose:
            click.echo("Combining {resource_name} resources into csv file: {file}".format(resource_name=resource_name,
                                                                                          file=os.path.join(target_dir, resource_name + '.csv')))
        if target_dir:
            outf = open(os.path.join(target_dir,
                resource_name + '.csv'), 'w', encoding='utf-8')
        outf.write("\N{bom}")
        dataset_type = get_dataset_type_for_resource_name(resource_name)
        if verbose:
            click.echo("Writing packages of type {dataset_type} into csv file: {file}".format(dataset_type=dataset_type,
                                                                                              file=os.path.join(target_dir, resource_name + '.csv')))
        _write_one_csv(
            lc,
            _get_packages(dataset_type, orgs),
            get_chromo(resource_name),
            outf)

        if target_dir:
            outf.close()


def _write_one_csv(lc, pkgs, chromo, outfile):
    out = csv.writer(outfile)
    column_ids = [f['datastore_id'] for f in chromo['fields'] if not f.get('published_resource_computed_field')
        ] + chromo.get('csv_org_extras', []) + [
        'owner_org', 'owner_org_title']
    out.writerow(column_ids)

    for pkg in pkgs:
        for res in pkg['resources']:
            if res['name'] == chromo['resource_name']:
                break
        else:
            click.echo('resource {0} not found for {1}'.format(
                chromo['resource_name'], pkg['owner_org']))
            continue

        org_extras = {
            'owner_org': pkg['owner_org'],
            'owner_org_title': pkg['org_title'],
        }
        if chromo.get('csv_org_extras'):
            org = lc.action.organization_show(id=pkg['owner_org'])
            for ename in chromo.get('csv_org_extras', []):
                org_extras[ename] = u''
                if ename in org:
                    org_extras[ename] = org[ename]
                else:
                    for e in org['extras']:
                        if e['key'] == ename:
                            org_extras[ename] = e['value']
                            break

        offs = 0
        while True:
            try:
                result = lc.action.datastore_search(
                    offset=offs,
                    limit=DATASTORE_PAGINATE,
                    sort='_id',
                    resource_id=res['id'],
                )
                records = result['records']
                total = result.get('total')
            except NotFound:
                click.echo('resource {0} table missing for {1}'.format(
                    chromo['resource_name'], pkg['owner_org']))
                break

            for record in records:
                record.update(org_extras)
                try:
                    row = [str(u'' if record[col] is None else
                           u','.join(record[col]) if isinstance(record[col], list) else
                           record[col]) for col in column_ids]
                    out.writerow(['\r\n'.join(col.splitlines()) for col in row])
                except KeyError:
                    click.echo('resource {0} table missing keys for {1}'.format(
                        chromo['resource_name'], pkg['owner_org']))
                    break

            if len(records) < DATASTORE_PAGINATE:
                break
            offs += DATASTORE_PAGINATE


def _remove_broken(target_datasets, verbose=False):
    """
    Low-level command to remove datasets with missing datastore tables
    """
    lc = LocalCKAN()
    for dtype in target_datasets:
        datasets = lc.action.package_search(q="type:%s" % dtype, include_private=True, rows=5000)
        for d in datasets['results']:
            for r in d['resources']:
                try:
                    lc.action.datastore_search(resource_id=r['id'], limit=0)
                except NotFound:
                    click.echo('removing %s %s' % (d['name'], d['title']))
                    lc.action.resource_delete(id=r['id'])
                    lc.action.package_delete(id=d['id'])
                    break


def _run_triggers(target_datasets, all_types=False, verbose=False):
    """
    Low-level command to run triggers on datasets' datastore tables
    """
    lc = LocalCKAN()
    for dtype in _expand_dataset_types(target_datasets, all_types):
        datasets = lc.action.package_search(q="type:%s" % dtype, include_private=True, rows=5000)
        for d in datasets['results']:
            for r in d['resources']:
                try:
                    results = lc.action.datastore_run_triggers(resource_id=r['id'])
                    click.echo(' '.join([r['name'], d['owner_org'], d['organization']['name'],
                               'updated', str(results), 'records']))
                except ValidationError as e:
                    click.echo(' '.join([r['name'], d['owner_org'], d['organization']['name'],
                               'failed', str(e.error_dict)]), err=True)


def _target_datasets(verbose=False):
    """
    Find the RecombinantPlugin instance and output its
    configured target datasets (e.g., ['ati', 'pd', ...])
    """
    click.echo(' '.join(get_target_datasets()))


def _dataset_types(dataset_types, verbose=False):
    """
    Output dataset types of recombinant resources
    """
    for t in _expand_dataset_types(dataset_types, all_types=False):
        click.echo(t + ': ' + ' '.join(
            c['resource_name'] for c in get_geno(t)['resources']))


def _template(dataset_type, org_name, output_file, verbose=False):
    """
    Output the recombinant excel template to a file path
    """
    lc = LocalCKAN()
    org = lc.action.organization_show(id=org_name)
    tmpl = excel_template(dataset_type, org)
    with open(output_file, 'w') as out:
        tmpl.save(out)
