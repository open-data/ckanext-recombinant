from collections import namedtuple
import re
from datetime import datetime

from ckanext.recombinant.errors import BadExcelData


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
    'year': DatastoreType('year', True, None, '###0'),
    'month': DatastoreType('month', True, None, '00'),
    'date': DatastoreType('date', False, None, 'yyyy-mm-dd'),
    'int': DatastoreType('int', True, None, '### ### ### ### ### ##0'),
    'bigint': DatastoreType('bigint', True, None, '### ### ### ### ### ##0'),
    'money': DatastoreType(
        'money',
        False,
        None,
        '### ### ### ### ### ##0'),
    'text': DatastoreType('text', False, None, '@'),
    'boolean': DatastoreType('boolean', False, None, '@'),
    '_text': DatastoreType('_text', False, None, '@'),
    'timestamp': DatastoreType('timestamp', False, None, 'General'),
}


def canonicalize(dirty, dstore_tag, primary_key):
    """
    Canonicalize dirty input from xlrd to align with
    recombinant.json datastore type specified in dstore_tag.

    :param dirty: dirty cell content as read through xlrd
    :type dirty: object
    :param dstore_tag: datastore_type specifier in (JSON) schema for cell
    :type dstore_tag: str
    :param primary_key: True if this field is part of the PK
    :type primary_key: bool

    :return: Canonicalized cell input
    :rtype: float or unicode

    Raises BadExcelData on formula cells
    """
    dtype = datastore_type[dstore_tag]
    if dstore_tag == '_text':
        if not dirty or not unicode(dirty).strip():
            return []
        return [s.strip() for s in unicode(dirty).split(',')]

    if dirty is None:
        return dtype.default
    elif isinstance(dirty, (float, int, long)):
        return unicode(dirty)

    elif isinstance(dirty, basestring) and not dirty.strip():
        # Content trims to empty: default
        return dtype.default
    elif not dtype.numeric:
        if dtype.tag == 'money':
            if unicode(dirty).startswith('='):
                raise BadExcelData('Formulas are not supported')
            # User has overridden Excel format string, probably adding currency
            # markers or digit group separators (e.g.,fr-CA uses 1$ (not $1)).
            # Accept only "DDDDD.DD", discard other characters
            dollars, sep, cents = unicode(dirty).rpartition('.')
            return re.sub(ur'[^0-9]', '', dollars) + sep + re.sub(ur'[^0-9]', '', cents)
        elif dtype.tag == 'date' and isinstance(dirty, datetime):
            return u'%04d-%02d-%02d' % (dirty.year, dirty.month, dirty.day)

        dirty = unicode(dirty)
        # accidental whitespace around primary keys leads to unpleasantness
        if primary_key:
            dirty = dirty.strip()

        # excel, you keep being you
        if dirty == u'=FALSE()':
            return u'FALSE'
        elif dirty == u'=TRUE()':
            return u'TRUE'
        elif dirty.startswith('='):
            raise BadExcelData('Formulas are not supported')
        return dirty

    # dirty is numeric: truncate trailing decimal digits, retain int part
    canon = re.sub(r'[^0-9]', '', unicode(dirty).split('.')[0])
    if not canon:
        return 0
    return unicode(canon) # FIXME ckan2.1 datastore?-- float(dirty)
