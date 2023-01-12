from ckan.plugins.toolkit import _, check_access

from ckanapi import LocalCKAN, NotFound, ValidationError, NotAuthorized
from ckan.logic import get_or_bust
from paste.deploy.converters import asbool

from ckanext.recombinant.tables import get_geno
from ckanext.recombinant.errors import RecombinantException
from ckanext.recombinant.datatypes import datastore_type
from ckanext.recombinant.helpers import _read_choices_file

import ckanext.datastore.logic.schema as dsschema
from ckanext.datastore.backend import DatastoreBackend
from ckanext.datastore.logic.action import _check_read_only, _validate


def recombinant_create(context, data_dict):
    '''
    Create a dataset with datastore table(s) for an organization and
    recombinant dataset type.

    :param dataset_type: recombinant dataset type
    :param owner_org: organization name or id
    '''
    lc, geno, results = _action_find_dataset(context, data_dict)

    if results:
        raise ValidationError({'owner_org':
            _("dataset type %s already exists for this organization")
            % data_dict['dataset_type']})

    resources = [
        # dummy url for old ckan compatibility reasons
        dict(_resource_fields(chromo), url='http://')
        for chromo in geno['resources']]

    dataset = lc.action.package_create(
        type=data_dict['dataset_type'],
        owner_org=data_dict['owner_org'],
        resources=resources,
        **_dataset_fields(geno))

    dataset = _update_dataset(lc, geno, dataset)
    return _update_datastore(lc, geno, dataset)


def recombinant_update(context, data_dict):
    '''
    Update a dataset's datastore table(s) for an organization and
    recombinant dataset type.

    :param dataset_type: recombinant dataset type
    :param owner_org: organization name or id
    :param delete_resources: True to delete extra resources found
    :param force_update: True to force updating of datastore tables
    '''
    lc, geno, dataset = _action_get_dataset(context, data_dict)

    dataset = _update_dataset(
        lc, geno, dataset,
        delete_resources=asbool(data_dict.get('delete_resources', False)))
    _update_datastore(
        lc, geno, dataset,
        force_update=asbool(data_dict.get('force_update', False)))


def recombinant_show(context, data_dict):
    '''
    Return the status of a recombinant dataset including all its tables
    and checking that its metadata is up to date.

    :param dataset_type: recombinant dataset type
    :param owner_org: organization name
    '''
    lc, geno, dataset = _action_get_dataset(context, data_dict)

    chromos = dict(
        (chromo['resource_name'], chromo) for chromo in geno['resources'])

    resources = []
    resources_correct = True

    for resource in dataset['resources']:
        out = {
            'id': resource['id'],
            'name': resource['name'],
            'description': resource['description'],
            }

        # migration below will update this
        metadata_correct = True
        if (len(chromos) == 1 and len(dataset['resources']) == 1
                and resource['name'] == 'data'):
            resource['name'] = geno['resources'][0]['resource_name']
            metadata_correct = False

        if resource['name'] not in chromos:
            out['error'] = 'unknown resource name'
            resources.append(out)
            continue

        r = chromos[resource['name']]
        metadata_correct = metadata_correct and _resource_match(r, resource)
        resources_correct = resources_correct and metadata_correct
        out['metadata_correct'] = metadata_correct

        try:
            ds = lc.action.datastore_search(
                resource_id=resource['id'],
                limit=1)
            datastore_correct = _datastore_match(r['fields'], ds['fields'])
            out['datastore_correct'] = datastore_correct
            resources_correct = resources_correct and datastore_correct
            out['datastore_rows'] = ds.get('total', 0)
        except NotFound:
            out['error'] = 'datastore table missing'
            resources_correct = False

        resources.append(out)

    metadata_correct = _dataset_match(geno, dataset)
    return {
        'dataset_type': dataset['type'],
        'owner_org': dataset['organization']['name'],
        'org_title': dataset['organization']['title'],
        'id': dataset['id'],
        'metadata_correct': metadata_correct,
        'all_correct': (metadata_correct and resources_correct
            and len(dataset['resources']) == len(chromos)),
        'resources': resources,
        'template_updated': geno.get('template_updated'),
        }


def _action_find_dataset(context, data_dict):
    '''
    common code for actions that need to check for a dataset based on
    the dataset type and organization name or id
    '''
    dataset_type = get_or_bust(data_dict, 'dataset_type')
    owner_org = get_or_bust(data_dict, 'owner_org')

    try:
        geno = get_geno(dataset_type)
    except RecombinantException:
        raise ValidationError({'dataset_type':
            _("Recombinant dataset type not found")})

    lc = LocalCKAN(username=context['user'])
    result = lc.action.package_search(
        q="type:%s AND organization:%s" % (dataset_type, owner_org),
        include_private=True,
        rows=2)
    return lc, geno, result['results']


def _action_get_dataset(context, data_dict):
    '''
    common code for actions that need to retrieve a dataset based on
    the dataset type and organization name or id
    '''
    lc, geno, results = _action_find_dataset(context, data_dict)

    if not results:
        raise NotFound()
    if len(results) > 1 and not data_dict.get('ignore_errors'):
        raise ValidationError({'owner_org':
            _("Multiple datasets exist for type {0} org {1}").format(
                 data_dict['dataset_type'], data_dict['owner_org'])})

    return lc, geno, results[0]


def _update_dataset(lc, geno, dataset, delete_resources=False):
    """
    call lc.action.package_update on dataset if necessary to make its
    metadata match the dataset definition geno
    """
    package_update_required = False
    if not _dataset_match(geno, dataset):
        dataset.update(_dataset_fields(geno))
        package_update_required = True

    chromos = dict(
        (chromo['resource_name'], chromo) for chromo in geno['resources'])

    # migrate recombinant1 datasets which had no resource
    # name to identify resource
    if (len(chromos) == 1 and len(dataset['resources']) == 1
            and dataset['resources'][0]['name'] == 'data'):
        dataset['resources'][0]['name'] = geno['resources'][0]['resource_name']
        package_update_required = True

    # collect updated resources
    out_resources = []
    for resource in dataset['resources']:
        if resource['name'] not in chromos:
            if not delete_resources:
                out_resources.append(resource)
            continue

        r = chromos.pop(resource['name'])

        if not _resource_match(r, resource):
            resource.update(_resource_fields(r))
            package_update_required = True

        out_resources.append(resource)

    # missing resources
    if chromos:
        out_resources.extend(
            # dummy url for old ckan compatibility reasons
            dict(_resource_fields(chromo), url='http://')
            for chromo in chromos.values())
        package_update_required = True

    if (package_update_required or
            len(out_resources) != len(dataset['resources'])):
        dataset['resources'] = out_resources
        dataset = lc.call_action('package_update', dataset)

    return dataset


def _update_datastore(lc, geno, dataset, force_update=False):
    """
    call lc.action.datastore_create to create tables or add
    columns to existing datastore tables based on dataset definition
    geno for existing dataset.
    """
    resource_ids = dict((r['name'], r['id']) for r in dataset['resources'])
    datastore_text_types = geno.get('datastore_text_types', False)

    for chromo in geno['resources']:
        assert chromo['resource_name'] in resource_ids, (
            "dataset missing resource for resource name",
            chromo['resource_name'], dataset['id'])
        resource_id = resource_ids[chromo['resource_name']]
        fields = datastore_fields(chromo['fields'], datastore_text_types)
        try:
            ds = lc.action.datastore_search(resource_id=resource_id, limit=0)
        except NotFound:
            pass
        else:
            if not force_update and _datastore_match(
                    chromo['fields'], ds['fields']):
                continue
            # extra work here to maintain existing fields+ordering
            # datastore_create rejects our list otherwise
            fields = ds['fields'][1:] # trim _id field
            seen = set(f['id'] for f in fields)
            for f in datastore_fields(chromo['fields'], datastore_text_types):
                if f['id'] not in seen:
                    fields.append(f)

        trigger_names = _update_triggers(lc, chromo)

        lc.action.datastore_create(
            resource_id=resource_id,
            fields=fields,
            primary_key=chromo.get('datastore_primary_key', []),
            indexes=chromo.get('datastore_indexes', []),
            triggers=[{'function': unicode(f)} for f in trigger_names],
            force=True)


def _update_triggers(lc, chromo):
    field_choices = {}
    trigger_names = []

    for f in chromo['fields']:
        if 'choices' in f:
            field_choices[f['datastore_id']] = sorted(f['choices'])
        elif 'choices_file' in f and '_path' in chromo:
            field_choices[f['datastore_id']] = sorted(_read_choices_file(chromo, f))

    for tr in chromo.get('triggers', []):
        if isinstance(tr, dict):
            assert len(tr) == 1, 'inline trigger may have only one key:' + repr(tr.keys())
            ((trname, trcode),) = tr.items()
            trigger_names.append(trname)
            try:
                lc.action.datastore_function_create(
                    name=unicode(trname),
                    or_replace=True,
                    rettype=u'trigger',
                    definition=unicode(trcode).format(**dict(
                        (fkey, _pg_array(fchoices))
                        for fkey, fchoices in field_choices.items())))
            except NotAuthorized:
                pass  # normal users won't be able to reset triggers
        else:
            trigger_names.append(tr)
    return trigger_names


def _pg_array(choices):
    try:
        from ckanext.datastore.backend.postgres import literal_string
    except ImportError:
        from ckanext.datastore.helpers import literal_string

    return u'ARRAY[' + u','.join(
        literal_string(unicode(c)) for c in choices) + u']'


def _dataset_fields(geno):
    """
    return the dataset metadata fields created for dataset definition geno
    """
    return {'title': geno['title'], 'notes': geno.get('notes', '')}


def _dataset_match(geno, dataset):
    """
    return True if dataset metadata matches expected fields for dataset type dt
    """
    return all(dataset[k] == v for (k, v) in _dataset_fields(geno).items())


def _resource_fields(chromo):
    """
    return the resource metadata fields created for resource definition chromo
    """
    return {
        'name': chromo['resource_name'],
        'description': chromo['title'],
        'url_type': u'datastore',
        }


def _resource_match(chromo, resource):
    """
    return True if resource metadatas matches expected fields for sheet r
    """
    return all(resource[k] == v for (k, v) in _resource_fields(chromo).items())


def datastore_column_type(t, text_types):
    """
    return postgres column type for field type t
    if text_types is true return simple types (almost all text) for backwards compatibility
    """
    if text_types:
        return 'bigint' if datastore_type[t].whole_number else 'text'
    if t == 'money':
        return 'numeric'
    return 'int' if t in ('year', 'month') else t


def datastore_fields(fs, text_types):
    """
    return the datastore field definitions for fields fs
    """
    return [{
        'id': f['datastore_id'],
        'type': datastore_column_type(f['datastore_type'], text_types)}
        for f in fs]


def _datastore_match(fs, fields):
    """
    return True if existing datastore column fields include fields
    defined in fs.
    """
    # XXX: does not check types or extra columns at this time
    existing = set(c['id'] for c in fields)
    return all(f['datastore_id'] in existing for f in fs)


def clear_datastore(context, data_dict):
    '''Clears rows in a table or a set of rows from the DataStore.

    :param resource_id: resource id that the data will be deleted from.
                        (required)
    :type resource_id: string
    :param force: set to True to edit a read-only resource
    :type force: bool (optional, default: False)
    :param filters: filters to apply before deleting 
                    (eg {"ref_number": "001-2018-2019-Q2-00045"}).
                    If missing delete all rows but keep table.
                    If filters are invalid, fails with Exception.
                    (optional)
    :type filters: dictionary

    **Results:**

    :returns: Original filters sent with resource_id
    :rtype: dictionary

    '''
    schema = context.get('schema', dsschema.datastore_upsert_schema())
    backend = DatastoreBackend.get_active_backend()

    # Remove any applied filters before running validation.
    filters = data_dict.pop('filters', None)
    data_dict, errors = _validate(data_dict, schema, context)

    if filters is not None:
        if not isinstance(filters, dict):
            raise ValidationError({'filters': ['filters must be either a dict or null.']})
        data_dict['filters'] = filters
    else:
        data_dict['filters'] = {}

    if errors:
        raise ValidationError(errors)

    check_access('datastore_delete', context, data_dict)

    if not data_dict.pop('force', False):
        resource_id = data_dict['resource_id']
        _check_read_only(context, resource_id)

    resource_id = data_dict['resource_id']

    if not backend.resource_exists(resource_id):
        raise NotFound(_(u'Resource "{0}" was not found.'.format(resource_id)))

    result = backend.delete(context, data_dict)

    result.pop('id', None)
    result.pop('connection_url', None)
    return result