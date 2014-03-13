import xlwt

from ckanext.recombinant.plugins import _get_tables
from ckanext.recombinant.errors import RecombinantException

XLS_0_WIDTH = 256  # width of '0' character in default font

def xls_template(dataset_type, org):
    """
    return an xlwn.Workbook object containing the sheet and header fields
    for passed dataset_type and org.
    """
    tables = _get_tables()
    for t in tables:
        if t['dataset_type'] == dataset_type:
            break
    else:
        raise RecombinantException('dataset_type "%s" not found'
            % dataset_type)

    book = xlwt.Workbook()
    sheet = book.add_sheet(t['xls_sheet_name'])
    org_xf = xlwt.easyxf(t['xls_organization_style'])
    for n, key in enumerate(t['xls_organization_info']):
        if not key:
            continue
        if key not in org:
            continue
        sheet.write(0, n, org[key], org_xf)
    header_xf = xlwt.easyxf(t['xls_header_style'])
    for n, field in enumerate(t['fields']):
        sheet.write(1, n, field['label'], header_xf)
        sheet.col(n).width = field['xls_column_width'] * XLS_0_WIDTH

    sheet.set_panes_frozen(True)  # frozen headings instead of split panes
    sheet.set_horz_split_pos(2)  # in general, freeze after last heading row
    sheet.set_remove_splits(True)  # if user does unfreeze, don't leave a split there
    return book

