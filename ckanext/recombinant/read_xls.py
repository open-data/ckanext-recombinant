
import re
import xlrd

# special place to look for the organization name in each XLS file
ORG_NAME_CELL = (0, 2)

def read_xls(f, file_contents = None):
    """
    Return a generator that opens the xls file f
    and then produces ((sheet-name, org-name), row1, row2, ...)
    """
    if file_contents is not None:
        wb = xlrd.open_workbook(file_contents= file_contents)
    else:
        wb = xlrd.open_workbook(f)
    assert wb.nsheets == 1

    sheet = wb.sheet_by_index(0)
    org_name_cell = sheet.cell(*ORG_NAME_CELL)
    yield (sheet.name, org_name_cell.value)

    row = sheet.horz_split_pos
    while row < sheet.nrows:
        # return next non-empty row
        if not all(_is_bumf(c.value) for c in sheet.row(row)):
            yield [c.value for c in sheet.row(row)]
        row += 1

def _is_bumf(value):
    """
    Return true if this value is filler, en route to skipping over empty lines
    """
    if type(value) in (unicode, str):
        return (value.strip() == '')
    return (value is None)

def _canonicalize(dirty, dstore_type):
    """
    Fix and return dirty input to align with recombinant.json datastore type,
    'int' or 'text'.

    The xlrd software interprets a purely numeric excel field as float,
    and anything other as unicode, independent of recombinant.json
    datastore type specification.
    """
    if dirty is None:
        return 0.0 if dstore_type == 'int' else u''
    elif isinstance(dirty, float) or isinstance(dirty, int):
        if dstore_type == 'text':
            if int(dirty) == dirty:
                return unicode(int(dirty))
            else:
                return unicode(dirty)
        return float(dirty)
    elif (('strip' in dir(dirty)) and
            (dirty.strip() == '') and
            (dstore_type == 'int')):
        return 0.0
    elif dstore_type == 'text':
        return unicode(dirty)

    # dirty should be numeric: truncate trailing decimal digits, retain int part
    canon = re.sub(r'[^0-9]', '', re.sub(r'\.[0-9 ]+$', '', str(dirty)))
    try:
        return float(canon)
    except:
        logging.warn(
            'Bad integer input [{0}], using best-guess [{1}]'.format(
                dirty,
                unicode(canon)))
        return unicode(canon)

def get_records(upload_data, fields):
    """
    Truncate/pad empty/missing records to expected row length, canonicalize
    cell content, and return resulting record list.
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

        records.append(dict((
                f['datastore_id'],
                _canonicalize(v, f['datastore_type']))
            for f, v in zip(fields, row)))

    return records
