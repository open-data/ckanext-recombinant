import json

from pylons import c
import ckanapi

from ckanext.recombinant.tables import get_chromo, get_geno
from ckanext.recombinant.errors import RecombinantException

def recombinant_get_chromo(resource_name):
    """
    Get the resource definition (chromo) for the given resource name
    """
    try:
        return get_chromo(resource_name)
    except RecombinantException:
        return

def recombinant_get_geno(dataset_type):
    """
    Get the dataset definition (geno) for thr given dataset type
    """
    try:
        return get_geno(dataset_type)
    except RecombinantException:
        return

def recombinant_primary_key_fields(resource_name):
    try:
        chromo = get_chromo(resource_name)
    except RecombinantException:
        return []
    return [
        f for f in chromo['fields']
        if f['datastore_id'] in t['datastore_primary_key']
        ]

def recombinant_example(sheet_name, doc_type, indent=2, lang='json'):
    """
    Return example data formatted for use in API documentation
    """
    chromo = recombinant_get_chromo(resource_name)
    if chromo and doc_type in chromo.get('examples', {}):
        data = chromo['examples'][doc_type]
    elif doc_type == 'sort':
        data = "request_date desc, file_number asc"
    elif doc_type == 'filters':
        data = {"resource": "doc", "priority": "high"}
    elif doc_type == 'filter_one':
        data = {"file_number": "86086"}
    else:
        data = {
            "request_date": "2016-01-01",
            "file_number": "42042",
            "resource": "doc",
            "prioroty": "low",
        }

    if not isinstance(data, (list, dict)):
        return json.dumps(data)

    left = ' ' * indent

    if lang == 'pythonargs':
        return ',\n'.join(
            "%s%s=%s" % (left, k, json.dumps(data[k]))
            for k in sorted(data))

    out = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
    return left[2:] + ('\n' + left[2:]).join(out.split('\n')[1:-1])

def recombinant_show_package(pkg):
    """
    return recombinant_show results for pkg
    """
    lc = ckanapi.LocalCKAN(username=c.user)
    return lc.action.recombinant_show(
        dataset_type=pkg['type'],
        owner_org=pkg['organization']['name'])
