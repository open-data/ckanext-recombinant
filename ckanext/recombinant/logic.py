from pylons.i18n import _

from ckanapi import LocalCKAN, NotFound, ValidationError
from ckan.logic import get_or_bust
from paste.deploy.converters import asbool

from ckanext.recombinant.tables import get_geno
from ckanext.recombinant.errors import RecombinantException
from ckanext.recombinant.datatypes import datastore_type


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
        q="type:%s organization:%s" % (dataset_type, owner_org),
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
    if len(results) > 1:
        raise ValidationError({'owner_org':
            _("Multiple datasets exist for type %s") % data_dict['dataset_type']})

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

        lc.action.datastore_create(
            resource_id=resource_id,
            fields=fields,
            primary_key=chromo.get('datastore_primary_key', []),
            indexes=chromo.get('datastore_indexes', []),
            triggers=[{'function': unicode(f)} for f in chromo.get('triggers', [])],
            force=True)


def _dataset_fields(geno):
    """
    return the dataset metadata fields created for dataset definition geno
    """
    notes = geno.get('alt_notes', geno.get('notes', ''))
    return {'title': geno['title'], 'notes': notes}


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
        return 'bigint' if datastore_type[t].numeric else 'text'
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
