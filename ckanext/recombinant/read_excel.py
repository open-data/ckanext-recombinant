import openpyxl
from datatypes import canonicalize

from ckanext.recombinant.errors import BadExcelData

HEADER_ROWS = 3

def read_excel(f, file_contents=None):
    """
    Return a generator that opens the excel file f (name or file object)
    and then produces ((sheet-name, org-name), row1, row2, ...)
    :param: f: file name or xlsx file object

    :return: Generator that opens the excel file f
    and then produces:
        (sheet-name, org-name, column_names, data_rows_generator)
        ...
    :rtype: generator
    """
    wb = openpyxl.load_workbook(f, read_only=True)

    for sheetname in wb.sheetnames:
        if sheetname == 'reference':
            return
        sheet = wb[sheetname]
        rowiter = sheet.rows
        organization_row = next(rowiter)

        label_row = next(rowiter)
        names_row = next(rowiter)

        yield (
            sheetname,
            organization_row[0].value,
            [c.value for c in names_row],
            _filter_bumf(rowiter))


def _filter_bumf(rowiter):
    i = HEADER_ROWS
    for row in rowiter:
        i += 1
        values = [c.value for c in row]
        # return next non-empty row
        if not all(_is_bumf(v) for v in values):
            yield i, values


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


def get_records(rows, fields):
    """
    Truncate/pad empty/missing records to expected row length, canonicalize
    cell content, and return resulting record list.

    :param upload_data: generator producing rows of content
    :type upload_data: generator
    :param fields: collection of fields specified in JSON schema
    :type fields: list or tuple

    :return: canonicalized records of specified upload data
    :rtype: tuple of dicts
    """
    records = []
    for n, row in rows:
        # trailing cells might be empty: trim row to fit
        while (row and
                (len(row) > len(fields)) and
                (row[-1] is None or row[-1] == '')):
            row.pop()
        while row and (len(row) < len(fields)):
            row.append(None) # placeholder: canonicalize once only, below

        try:
            records.append(
                (n, dict((
                    f['datastore_id'],
                    canonicalize(v, f['datastore_type']))
                for f, v in zip(fields, row))))
        except BadExcelData, e:
            raise BadExcelData(u'Row {0}:'.format(n) + u' ' + e.message)

    return records
