from ckanapi import LocalCKAN, NotFound, ValidationError
from ckan.logic import get_or_bust
from paste.deploy.converters import asbool

from ckanext.recombinant.tables import get_dataset_type
from ckanext.recombinant.errors import RecombinantException
from ckanext.recombinant.datatypes import datastore_type


def recombinant_create(context, data_dict):
    '''
    Create a dataset with datastore table(s) for an organization and
    recombinant dataset type.

    :param dataset_type: recombinant dataset type
    :param owner_org: organization name or id
    '''
    lc, dt, results = _action_find_dataset(context, data_dict)

    if results:
        raise ValidationError({'owner_org':
            _("dataset type %s already exists for this organization")
            % dataset_type})

    resources = [_resource_fields(r) for r in dt['resources']]

    dataset = lc.action.package_create(
        type=dataset_type,
        owner_org=org['id'],
        resources=resources,
        **_dataset_fields(dt))

    dataset = _update_tables(lc, dt, dataset)
    return _update_datastore(lc, dt, dataset)


def recombinant_update(context, data_dict):
    '''
    Update a dataset's datastore table(s) for an organization and
    recombinant dataset type.

    :param dataset_type: recombinant dataset type
    :param owner_org: organization name or id
    :param delete_resources: True to delete extra resources found
    '''
    lc, dt, dataset = _action_get_dataset(context, data_dict)

    dataset = _update_dataset(
        lc, dt, dataset,
        delete_resources=asbool(data_dict.get('delete_resources', False)))
    _update_datastore(lc, dt, dataset)


def recombinant_show(context, data_dict):
    '''
    Return the status of a recombinant dataset including all its tables
    and checking that its metadata is up to date.

    :param dataset_type: recombinant dataset type
    :param owner_org: organization name or id
    '''
    lc, dt, dataset = _action_get_dataset(context, data_dict)

    tables = dict((r['sheet_name'], r) for r in dt['resources'])

    resources = []
    resources_correct = True

    for resource in dataset['resources']:
        out = {'id': resource['id'], 'name': resource['name']}

        # migration below will update this
        metadata_correct = True
        if (len(tables) == 1 and len(dataset['resources']) == 1
                and resource['name'] == 'data'):
            resource['name'] = dt['resources'][0]['sheet_name']
            metadata_correct = False

        if resource['name'] not in tables:
            out['error'] = 'unknown sheet name'
            resources.append(out)
            continue

        r = tables[resource['name']]
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

    metadata_correct = _dataset_match(dt, dataset)
    return {
        'dataset_type': dataset['type'],
        'owner_org': dataset['organization']['name'],
        'id': dataset['id'],
        'metadata_correct': metadata_correct,
        'all_correct': metadata_correct and resources_correct,
        'resources': resources,
        }


def _action_find_dataset(context, data_dict):
    '''
    common code for actions that need to check for a dataset based on
    the dataset type and organization name or id
    '''
    dataset_type = get_or_bust(data_dict, 'dataset_type')
    owner_org = get_or_bust(data_dict, 'owner_org')

    try:
        dt = get_dataset_type(dataset_type)
    except RecombinantException:
        raise ValidationError({'dataset_type':
            _("Recombinant dataset type not found")})

    lc = LocalCKAN(username=context['user'])
    result = lc.action.package_search(
        q="type:%s organization:%s" % (dataset_type, owner_org),
        rows=2)
    return lc, dt, result['results']


def _action_get_dataset(context, data_dict):
    '''
    common code for actions that need to retrieve a dataset based on
    the dataset type and organization name or id
    '''
    lc, dt, results = _action_find_dataset(context, data_dict)

    if not results:
        raise NotFound()
    if len(results) > 1:
        raise ValidationError({'owner_org':
            _("Multiple datasets exist for type %s") % dataset_type})

    return lc, dt, results[0]


def _update_dataset(lc, dt, dataset, delete_resources=False):
    """
    call lc.action.package_update on dataset if necessary to make its
    metadata match the dataset type dt
    """
    package_update_required = False
    if not _dataset_match(dt, dataset):
        dataset.update(_dataset_fields(dt))
        package_update_required = True

    tables = dict((r['sheet_name'], r) for r in dt['resources'])

    # migrate recombinant1 datasets which had no resource
    # name to identify resource
    if (len(tables) == 1 and len(dataset['resources']) == 1
            and dataset['resources'][0]['name'] == 'data'):
        dataset['resources'][0]['name'] = dt['resources'][0]['sheet_name']
        package_update_required = True

    # collect updated resources
    out_resources = []
    for resource in dataset['resources']:
        if resource['name'] not in tables:
            if not delete_resources:
                out_resources.append(resource)
            continue

        r = tables.pop(resource['name'])

        if not _resource_match(r, resource):
            resource.update(_resource_fields(r))
            package_update_required = True

        out_resources.append(resource)

    # missing resources
    if tables:
        out_resources.extend(_resource_fields[r] for r in tables)
        package_update_required = True

    if (package_update_required or
            len(out_resources) != len(dataset['resources'])):
        dataset['resources'] = out_resources
        dataset = lc.call_action('package_update', dataset)

    return dataset


def _update_datastore(lc, dt, dataset):
    """
    call lc.action.datastore_create to create tables or add
    columns to existing datastore tables based on dataset type
    dt for existing dataset.
    """
    resource_ids = dict((r['name'], r['id']) for r in dataset['resources'])

    for r in dt['resources']:
        assert r['sheet_name'] in resource_ids, (
            "dataset missing resource for sheet",
            r['sheet_name'], dataset['id'])
        resource_id = resource_ids[r['sheet_name']]
        fields = _datastore_fields(r['fields'])
        try:
            ds = lc.action.datastore_search(resource_id=resource_id, limit=0)
        except NotFound:
            pass
        else:
            if _datastore_match(r['fields'], ds['fields']):
                continue
            # extra work here to maintain existing fields+ordering
            # datastore_create rejects our list otherwise
            fields = ds['fields'][1:] # trim _id field
            seen = set(f['id'] for f in fields)
            for f in _datastore_fields(r['fields']):
                if f['id'] not in seen:
                    fields.append(f)

        lc.action.datastore_create(resource_id=resource_id, fields=fields)


def _dataset_fields(dt):
    """
    return the dataset metadata fields created for dataset type dt
    """
    return {'title': dt['title'], 'notes': dt.get('notes', '')}


def _dataset_match(dt, dataset):
    """
    return True if dataset metadata matches expected fields for dataset type dt
    """
    return all(dataset[k] == v for (k, v) in _dataset_fields(dt).items())


def _resource_fields(r):
    """
    return the resource metadata fields create for sheet r
    """
    return {'name': r['sheet_name'], 'description': r['title'], 'url': 'http://'}


def _resource_match(r, resource):
    """
    return True if resource metadatas matches expected fields for sheet r
    """
    return all(resource[k] == v for (k, v) in _resource_fields(r).items())


def _column_type(t):
    """
    return postgres column type for field type t
    """
    return 'bigint' if datastore_type[t].numeric else 'text'


def _datastore_fields(fs):
    """
    return the datastore field definitions for fields fs
    """
    return [{
        'id': f['datastore_id'],
        'type': _column_type(f['datastore_type'])}
        for f in fs]


def _datastore_match(fs, fields):
    """
    return True if existing datastore column fields include fields
    defined in fs.
    """
    # XXX: does not check types or extra columns at this time
    existing = set(c['id'] for c in fields)
    return all(f['datastore_id'] in existing for f in fs)
