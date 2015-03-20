from collections import namedtuple


class DataStoreType(namedtuple(
        'DataStoreType',
        ['tag', 'numeric', 'default', 'xl_format'])):
    """
    Codifies data store types available in recombinant-tables JSON
    specification:
        'tag': the content of the datastore_type value
        'numeric': if content is a number, whether to retain
            trailing .0 padding for xlrd float coercion
        'default': default value to use if blank
        'xl_format': Excel custom format string to apply
    """
    pass

data_store_type = {
    'year': DataStoreType('year', True, 0.0, '###0'),
    'month': DataStoreType('month', True, 0.0, '00'),
    'date': DataStoreType('date', False, u'', 'yyyy-mm-dd'),
    'int': DataStoreType('int', True, 0.0, '### ### ### ### ### ##0'),
    'money': DataStoreType(
        'money',
        False,
        u'',
        '[<1000]$##0;[<1000000]$### ##0;$### ### ##0'),
    'text': DataStoreType('text', False, u'', None)}
