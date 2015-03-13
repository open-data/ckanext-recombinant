
import re
import xlrd
from datetime import datetime, date
from datatypes import  data_store_type

# special place to look for the organization name in each XLS file
ORG_NAME_CELL = (0, 2)


def read_xls(f, file_contents=None):
    """
    Return a generator that opens the xls file f
    and then produces ((sheet-name, org-name, date-mode), row1, row2, ...)
    :param: f: file name
    :type f: string
    :param: file_contents: content of workbook
    :type file_contents: string

    :return: Generator that opens the xls file f
    and then produces ((sheet-name, org-name, date-mode), row1, row2, ...)
    :rtype: generator
    """
    if file_contents is not None:
        wb = xlrd.open_workbook(file_contents= file_contents)
    else:
        wb = xlrd.open_workbook(f)
    assert wb.nsheets == 1

    sheet = wb.sheet_by_index(0)
    org_name_cell = sheet.cell(*ORG_NAME_CELL)
    yield (sheet.name, org_name_cell.value, wb.datemode)

    row = sheet.horz_split_pos
    while row < sheet.nrows:
        # return next non-empty row
        if not all(_is_bumf(c.value) for c in sheet.row(row)):
            yield [c.value for c in sheet.row(row)]
        row += 1


def _is_bumf(value):
    """
    Return true if this value is filler, en route to skipping over empty lines

    :param value: value to check
    :type value: object

    :return: whether the value is filler
    :rtype: bool
    """
    if type(value) in (unicode, str):
        return value.strip() == ''
    return value is None


def _canonicalize(dirty, dstore_tag, date_mode):
    """
    Canonicalize dirty input from xlrd to align with
    recombinant.json datastore type specified in dstore_tag.

    The date_mode adheres to the xlrd Excel workbook; it has value 1
    if the workbook originates on Excel for Macinstosh and 0 otherwise.

    :param dirty: dirty cell content as read through xlrd
    :type dirty: object
    :param dstore_tag: datastore_type specifier in (JSON) schema for cell
    :type dstore_tag: str
    :param date_mode: Excel workbook date mode attribute
    :type date_mode: integer

    :return: Canonicalized cell input
    :rtype: float or unicode
    """
    dtype = data_store_type[dstore_tag]
    if dirty is None:
        return dtype.default
    elif isinstance(dirty, float) or isinstance(dirty, int):
        if dtype.numeric:
            return float(dirty)
        elif dtype.tag == 'date':
            # excel returns dates as floats - convert back
            dt = datetime(*xlrd.xldate_as_tuple(dirty, date_mode))
            return unicode(dt.date())
        else:
            # JSON specifies text or money: content of origin is numeric string.
            # If xlrd has added .0 to present content as a float,
            # trim it before returning as numeric string
            if int(dirty) == dirty:
                return unicode(int(dirty))
            else:
                return unicode(dirty)
    elif (isinstance(dirty, basestring)) and (dirty.strip() == ''):
        # Content trims to empty: default
        return dtype.default
    elif not dtype.numeric:
        if dtype.tag == 'money':
            # User has overridden Excel format string, probably adding currency
            # markers or digit group separators (e.g.,fr-CA uses 1$ (not $1)).
            # Truncate any trailing decimal digits, retain int
            # part, and cast as numeric string.
            canon = re.sub(r'[^0-9]', '', re.sub(r'\.[0-9 ]+$', '', str(dirty)))
            return unicode(canon)
        return unicode(dirty)

    # dirty is numeric: truncate trailing decimal digits, retain int part
    canon = re.sub(r'[^0-9]', '', re.sub(r'\.[0-9 ]+$', '', str(dirty)))
    return float(canon)


def get_records(upload_data, fields, date_mode):
    """
    Truncate/pad empty/missing records to expected row length, canonicalize
    cell content, and return resulting record list.

    :param upload_data: generator producing rows of content
    :type upload_data: generator
    :param fields: collection of fields specified in JSON schema
    :type fields: list or tuple
    :param date_mode: Excel workbook date mode attribute
    :type date_mode: int

    :return: canonicalized records of specified upload data
    :rtype: tuple of dicts
    """
    records = []
    for n, row in enumerate(upload_data):
        # trailing cells might be empty: trim row to fit
        while (row and
                (len(row) > len(fields)) and
                (row[-1] is None or row[-1] == '')):
            row.pop()
        while row and (len(row) < len(fields)):
            row.append(None) # placeholder: canonicalize once only, below

        records.append(
            dict((
                f['datastore_id'],
                _canonicalize(v, f['datastore_type'], date_mode))
            for f, v in zip(fields, row)))

    return records
