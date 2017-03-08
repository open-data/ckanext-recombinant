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
    '_text': DatastoreType('_text', False, u'', 'General'),
}


def canonicalize(dirty, dstore_tag):
    """
    Canonicalize dirty input from xlrd to align with
    recombinant.json datastore type specified in dstore_tag.

    :param dirty: dirty cell content as read through xlrd
    :type dirty: object
    :param dstore_tag: datastore_type specifier in (JSON) schema for cell
    :type dstore_tag: str

    :return: Canonicalized cell input
    :rtype: float or unicode

    Raises BadExcelData on formula cells
    """
    dtype = datastore_type[dstore_tag]
    if dirty is None:
        return dtype.default
    elif isinstance(dirty, (float, int, long)):
        return unicode(dirty)

    elif isinstance(dirty, basestring) and not dirty.strip():
        # Content trims to empty: default
        return dtype.default
    elif not dtype.numeric:
        if dtype.tag == 'money':
            # User has overridden Excel format string, probably adding currency
            # markers or digit group separators (e.g.,fr-CA uses 1$ (not $1)).
            # Accept only "DDDDD.DD", discard other characters
            dollars, sep, cents = unicode(dirty).rpartition('.')
            return re.sub(ur'[^0-9]', '', dollars) + sep + re.sub(ur'[^0-9]', '', cents)
        elif dtype.tag == 'date' and isinstance(dirty, datetime):
            return u'%04d-%02d-%02d' % (dirty.year, dirty.month, dirty.day)

        if unicode(dirty).startswith('='):
            raise BadExcelData('Formulas are not supported')
        return unicode(dirty)

    # dirty is numeric: truncate trailing decimal digits, retain int part
    canon = re.sub(r'[^0-9]', '', unicode(dirty).split('.')[0])
    if not canon:
        return 0
    return unicode(canon) # FIXME ckan2.1 datastore?-- float(dirty)
