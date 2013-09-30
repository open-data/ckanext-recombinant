
import xlrd


# special place to look for the organization name in each XLS file
ORG_NAME_CELL = (0, 3)

def read_xls(f, sheet_name):
    """
    Return a generator that opens the xls file f to sheet sheet_name
    and then produces (org-name, row1, row2, ...)
    """
    wb = xlrd.open_workbook(f)
    sheet = wb.sheet_by_name(sheet_name)
    org_name_cell = sheet.cell(*ORG_NAME_CELL)
    yield org_name_cell.value

    row = sheet.horz_split_pos
    while row < sheet.nrows:
        yield [c.value for c in sheet.row(row)]
        row += 1


