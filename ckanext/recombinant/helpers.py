import json

from ckanext.recombinant.tables import get_table, get_dataset_type
from ckanext.recombinant.errors import RecombinantException

def recombinant_get_table(sheet_name):
    try:
        return get_table(sheet_name)
    except RecombinantException:
        return

def recombinant_get_dataset_type(dataset_type):
    try:
        return get_dataset_type(dataset_type)
    except RecombinantException:
        return

def recombinant_primary_key_fields(sheet_name):
    try:
        t = get_table(sheet_name)
    except RecombinantException:
        return []
    return [
        f for f in t['fields']
        if f['datastore_id'] in t['datastore_primary_key']
        ]

def recombinant_example(sheet_name, doc_type, indent=2, lang='json'):
    """
    Return example data formatted for use in API documentation
    """
    t = recombinant_get_table(sheet_name)
    if t and doc_type in t.get('examples', {}):
        data = t['examples'][doc_type]
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
