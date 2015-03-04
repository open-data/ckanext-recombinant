
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

def clean_num(dirty):
    if isinstance(dirty, float):
        return dirty
    elif isinstance(dirty, int):
        return float(dirty)
    elif 'strip' in dir(dirty) and dirty.strip() == '':
        return dirty.strip()

    clean = re.sub(r'[^0-9]', '', re.sub(r'\.0$', '', str(dirty)))
    # clean = re.sub(r'[^0-9]', '', clean)
    try:
        return float(clean)
    except:
        logging.warn(
            'Bad integer input [{0}], using best-guess [{1}]'.format(
                dirty,
                clean))
        return clean
