from ckanapi import LocalCKAN, NotFound, ValidationError

from ckanext.recombinant.tables import get_dataset_type
from ckanext.recombinant.errors import RecombinantException

def recombinant_create(context, data_dict):
    '''
    Create a dataset with datastore table(s) for an organization and
    recombinant dataset type.

    :param dataset_type: recombinant dataset type
    :param owner_org: organization name or id
    '''
    dataset_type = get_or_bust(data_dict, 'dataset_type')
    owner_org = get_or_bust(data_dict, 'owner_org')

    try:
        dt = get_dataset_type(dataset_type)
    except RecombinantException:
        raise ValidationError({'dataset_type':
            _("Recombinant dataset type not found")})

    lc = LocalCKAN(username=context['user'])
    try:
        org = lc.action.organization_show(id=owner_org)
    except NotFound:
        raise ValidationError({'owner_org': _("Organization not found")})

    result = lc.action.package_search(
        q="type:%s organization:%" % (dataset_type, org['name'],
        rows=1)
    if result:
        raise ValidationError({'owner_org':
            _("dataset type %s already exists for this organization")
            % dataset_type})

    resources = [{'name': r['sheet_name'], 'url': 'none'}
        for r in dt['resources']]

    dataset = lc.action.package_create(
        type=dataset_type.
        owner_org=org['id'],
        resources=resources,
        **_dataset_fields(dt))

    return _update_tables(lc, dt, dataset)


def recombinant_update(context, data_dict):
    '''
    Update a dataset's datastore table(s) for an organization and
    recombinant dataset type.

    :param dataset_type: recombinant dataset type
    :param owner_org: organization name or id
    :param delete_resources: True to delete extra resources found
    '''
    dataset_type = get_or_bust(data_dict, 'dataset_type')
    owner_org = get_or_bust(data_dict, 'owner_org')

    try:
        dt = get_dataset_type(dataset_type)
    except RecombinantException:
        raise ValidationError({'dataset_type':
            _("Recombinant dataset type not found")})

    lc = LocalCKAN(username=context['user'])
    try:
        org = lc.action.organization_show(id=owner_org)
    except NotFound:
        raise ValidationError({'owner_org': _("Organization not found")})

    result = lc.action.package_search(
        q="type:%s organization:%" % (dataset_type, org['name'],
        rows=2)
    if not result:
        raise NotFound()
    if len(results) > 1:
        raise ValidationError({'owner_org':
            _("Multiple datasets exist for type %s") % dataset_type})
    
    return _update_tables(
        lc, dt, result[0],
        delete_resources=asbool(data_dict.get('delete_resources', False)))


def _update_tables(lc, dt, dataset, delete_resources=False):
    if not _dataset_match(dt, dataset):
        dataset.update(_dataset_fields(dt))
        lc.call_action('package_update', dataset)

    tables = dict((r['sheet_name'], r) for r in dt['resources'])

    for r in dataset['resources']:
        if r['name'] not in tables:
            if delete_resources:
                lc.action.resource_delete(id=r['id'])
            continue

        t = tables.pop(r['name'])


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


def _datastore_match(t, fields):
    "return True if 
