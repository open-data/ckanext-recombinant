
import xlrd


# special place to look for the organization name in each XLS file
ORG_NAME_CELL = (0, 2)

def read_xls(f):
    """
    Return a generator that opens the xls file f
    and then produces ((sheet-name, org-name), row1, row2, ...)
    """
    wb = xlrd.open_workbook(f)
    assert wb.nsheets == 1

    sheet = wb.sheet_by_index(0)
    org_name_cell = sheet.cell(*ORG_NAME_CELL)
    yield (sheet.name, org_name_cell.value)

    row = sheet.horz_split_pos
    while row < sheet.nrows:
        yield [c.value for c in sheet.row(row)]
        row += 1


