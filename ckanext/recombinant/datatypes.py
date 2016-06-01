from collections import namedtuple


# Codifies data store types available in recombinant-tables JSON
# specification:
#    'tag': the content of the datastore_type value
#    'numeric': if content is a number, whether to retain
#        trailing .0 padding for xlrd float coercion
#    'default': default value to use if blank
#    'xl_format': Excel custom format string to apply

DatastoreType = namedtuple(
        'DataStoreType',
        ['tag', 'numeric', 'default', 'xl_format'])

datastore_type = {
    'year': DatastoreType('year', True, 0.0, '###0'),
    'month': DatastoreType('month', True, 0.0, '00'),
    'date': DatastoreType('date', False, u'', 'yyyy-mm-dd'),
    'int': DatastoreType('int', True, 0.0, '### ### ### ### ### ##0'),
    'money': DatastoreType(
        'money',
        False,
        u'',
        '[<1000]$##0;[<1000000]$### ##0;$### ### ##0'),
    'text': DatastoreType('text', False, u'', '@'),
    'boolean': DatastoreType('boolean', False, u'', 'General'),
}
