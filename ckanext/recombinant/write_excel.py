import openpyxl

from ckanext.recombinant.tables import get_geno
from ckanext.recombinant.errors import RecombinantException
from ckanext.recombinant.datatypes import datastore_type
from ckanext.recombinant.helpers import (
    recombinant_choice_fields, recombinant_language_text)

from ckan.plugins.toolkit import _

white_font = openpyxl.styles.Font(color=openpyxl.styles.colors.WHITE)

def excel_template(dataset_type, org):
    """
    return an openpyxl.Workbook object containing the sheet and header fields
    for passed dataset_type and org.
    """
    geno = get_geno(dataset_type)

    book = openpyxl.Workbook()
    sheet = book.active
    refs = []
    for chromo in geno['resources']:
        _populate_excel_sheet(sheet, chromo, org, refs)
        sheet = book.create_sheet()

    _populate_reference_sheet(sheet, chromo, refs)
    sheet.title = 'reference'
    return book


def excel_data_dictionary(chromo):
    """
    return an openpyxl.Workbook object containing the field reference
    from chromo, one sheet per language
    """
    book = openpyxl.Workbook()
    sheet = book.active

    style1 = {
        'PatternFill': {
            'patternType': 'solid',
            'fgColor': 'FFFFF056'},
        'Font': {
            'bold': True}}
    style2 = {
        'PatternFill': {
            'patternType': 'solid',
            'fgColor': 'FFDFE2DB'}}

    from pylons import config
    from ckan.lib.i18n import handle_request, get_lang
    from ckan.common import c, request

    for lang in config['ckan.locales_offered'].split():
        if sheet is None:
            sheet = book.create_sheet()

        sheet.title = lang.upper()
        # switch language (FIXME: this is harder than it should be)
        request.environ['CKAN_LANG'] = lang
        handle_request(request, c)
        choice_fields = dict(
            (f['datastore_id'], f['choices'])
            for f in recombinant_choice_fields(chromo['resource_name']))

        refs = []
        for field in chromo['fields']:
            _append_field_ref_rows(refs, field, style1, style2)

            if field['datastore_id'] in choice_fields:
                _append_field_choices_rows(
                    refs,
                    choice_fields[field['datastore_id']])

        _populate_reference_sheet(sheet, chromo, refs)
        sheet = None

    return book


def _populate_excel_sheet(sheet, chromo, org, refs):
    """
    Format openpyxl sheet for the resource definition chromo and org.

    refs - list of rows to add to reference sheet, modified
        in place from this function

    returns field information for reference sheet
    """
    boolean_validator = openpyxl.worksheet.datavalidation.DataValidation(
        type="list", formula1='"FALSE,TRUE"', allow_blank=True)
    sheet.add_data_validation(boolean_validator)

    sheet.title = chromo['resource_name']

    def fill_cell(row, column, value, styles):
        c = sheet.cell(row=row, column=column)
        c.value = value
        apply_styles(styles, c)

    org_style = dict(
        chromo['excel_organization_style'],
        Alignment={'vertical': 'center'})
    fill_cell(1, 1, org['name'], org_style)
    fill_cell(
        1,
        2,
        recombinant_language_text(chromo['title']) + '        ' + org['title'],
        org_style)
    sheet.row_dimensions[1].height = 24
    apply_styles(org_style, sheet.row_dimensions[1])

    header_style = chromo['excel_header_style']
    error_color = chromo.get('excel_error_background_color', '763626')
    required_color = chromo.get('excel_required_border_color', '2A3132')

    error_fill = openpyxl.styles.PatternFill(
        start_color='FF%s' % error_color,
        end_color='FF%s' % error_color,
        fill_type='solid')
    required_side = openpyxl.styles.Side(
        style='medium',
        color='FF%s' % required_color)
    required_border = openpyxl.styles.Border(
        required_side, required_side, required_side, required_side)


    choice_fields = dict(
        (f['datastore_id'], f['choices'])
        for f in recombinant_choice_fields(chromo['resource_name']))

    pk_cells = [
        openpyxl.cell.get_column_letter(n)+'4' for
        n, field in enumerate((f for f in chromo['fields'] if f.get(
                    'import_template_include', True)), 1)
        if field['datastore_id'] in chromo['datastore_primary_key']]

    for n, field in enumerate((f for f in chromo['fields'] if f.get(
            'import_template_include', True)), 1):
        fill_cell(2, n, recombinant_language_text(field['label']), header_style)
        fill_cell(3, n, field['datastore_id'], header_style)
        # jumping through openpyxl hoops:
        col_letter = openpyxl.cell.get_column_letter(n)
        col = sheet.column_dimensions[col_letter]
        col.width = field['excel_column_width']
        # FIXME: format only below header
        col.number_format = datastore_type[field['datastore_type']].xl_format
        validation_range = '{0}4:{0}1004'.format(col_letter)

        _append_field_ref_rows(refs, field, org_style, header_style)

        if field['datastore_type'] == 'boolean':
            boolean_validator.ranges.append(validation_range)
        if field['datastore_type'] == 'date':
            sheet.conditional_formatting.add(validation_range,
                openpyxl.formatting.FormulaRule([
                        'AND(NOT(ISBLANK({cell})),NOT(ISNUMBER({cell})))'
                        .format(cell=col_letter + '4',)],
                    stopIfTrue=True,
                    fill=error_fill,
                    font=white_font,
                    ))
            sheet.conditional_formatting.add("{0}2".format(col_letter),
                openpyxl.formatting.FormulaRule([
                        'SUMPRODUCT(--NOT(ISBLANK({cells})),'
                        '--NOT(ISNUMBER({cells})))'
                        .format(cells=validation_range,)],
                    stopIfTrue=True,
                    fill=error_fill,
                    font=white_font,
                    ))

        if field['datastore_id'] in choice_fields:
            ref1 = len(refs) + 1
            _append_field_choices_rows(
                refs,
                choice_fields[field['datastore_id']],
                sheet.title + '!' + validation_range
                if field['datastore_type'] == '_text' else None)
            refN = len(refs)

            choice_range = 'reference!$B${0}:$B${1}'.format(ref1, refN)

            choices = [c[0] for c in choice_fields[field['datastore_id']]]
            if field['datastore_type'] == '_text':
                # custom validation only works in Excel, use conditional
                # formatting for libre office compatibility
                sheet.conditional_formatting.add(validation_range,
                    openpyxl.formatting.FormulaRule([(
                        # count characters in the cell
                        'IF(SUBSTITUTE({col}4," ","")="",0,'
                        'LEN(SUBSTITUTE({col}4," ",""))+1)-'
                        # minus length of valid choices
                        'SUMPRODUCT(--ISNUMBER(SEARCH('
                        '","&{r}&",",SUBSTITUTE(","&{col}4&","," ",""))),'
                        'LEN({r})+1)'
                        .format(
                            col=col_letter,
                            r=choice_range)
                        )],
                    stopIfTrue=True,
                    fill=error_fill,
                    font=white_font,
                    ))
            else:
                v = openpyxl.worksheet.datavalidation.DataValidation(
                    type="list",
                    formula1=choice_range,
                    allow_blank=True)
                v.errorTitle = u'Invalid choice'
                valid_keys = u', '.join(unicode(c) for c in choices)
                if len(valid_keys) < 40:
                    v.error = (u'Please enter one of the valid keys: '
                        + valid_keys)
                else:
                    v.error = (u'Please enter one of the valid keys shown on '
                        'sheet "reference" rows {0}-{1}'.format(ref1, refN))
                sheet.add_data_validation(v)
                v.ranges.append(validation_range)

            # hilight header if bad values pasted below
            if field['datastore_type'] == '_text':
                choice_counts = 'reference!$J${0}:$J${1}'.format(ref1, refN)
                sheet.conditional_formatting.add("{0}2".format(col_letter),
                    openpyxl.formatting.FormulaRule([(
                            # count characters in the validation range
                            'SUMPRODUCT(IF(SUBSTITUTE({v}," ","")="",0,'
                            'LEN(SUBSTITUTE({v}," ",""))+1))-'
                            # minus length of all valid choices found
                            'SUMPRODUCT({counts},LEN({choices})+1)'
                            .format(
                                v=validation_range,
                                col=col_letter,
                                choices=choice_range,
                                counts=choice_counts)
                            )],
                        stopIfTrue=True,
                        fill=error_fill,
                        font=white_font,
                        ))
            else:
                sheet.conditional_formatting.add("{0}2".format(col_letter),
                    openpyxl.formatting.FormulaRule([(
                            'COUNTIF({0},"<>"&"")' # all non-blank cells
                            '-SUMPRODUCT(COUNTIF({0},{1}))'
                            .format(validation_range, choice_range))],
                        stopIfTrue=True,
                        fill=error_fill,
                        font=white_font,
                        ))

        if field.get('excel_required'):
            # hilight missing values
            if field['datastore_id'] in chromo['datastore_primary_key']:
                sheet.conditional_formatting.add(validation_range,
                    openpyxl.formatting.FormulaRule([(
                            'AND({col}4="",SUMPRODUCT(LEN(A4:Z4)))'
                            .format(col=col_letter)
                            )],
                        stopIfTrue=True,
                        border=required_border,
                        ))
            else:
                sheet.conditional_formatting.add(validation_range,
                    openpyxl.formatting.FormulaRule([(
                            'AND({col}4="",{pk_vals})'
                            .format(
                                col=col_letter,
                                pk_vals='+'.join('LEN(%s)'%c for c in pk_cells))
                            )],
                        stopIfTrue=True,
                        border=required_border,
                        ))
        if field.get('excel_cell_error_formula'):
            sheet.conditional_formatting.add(validation_range,
                openpyxl.formatting.FormulaRule([
                    field['excel_cell_error_formula'].format(
                        cell=col_letter + '4',)
                    ],
                stopIfTrue=True,
                fill=error_fill,
                font=white_font,
                ))
        if field.get('excel_header_error_formula'):
            sheet.conditional_formatting.add("{0}2".format(col_letter),
                openpyxl.formatting.FormulaRule([
                        field['excel_header_error_formula'].format(
                            cells=validation_range,
                            column=col_letter,
                        )],
                    stopIfTrue=True,
                    fill=error_fill,
                    font=white_font,
                    ))

    apply_styles(header_style, sheet.row_dimensions[2])
    apply_styles(header_style, sheet.row_dimensions[3])
    sheet.row_dimensions[3].hidden = True

    sheet.freeze_panes = sheet['A4']


def _append_field_ref_rows(refs, field, style1, style2):
    refs.append((None, None, []))
    refs.append((style1, 24, [
        _('Field Name'),
        recombinant_language_text(field['label'])]))
    refs.append((style2, None, [
        _('ID'),
        field['datastore_id']]))
    if 'description' in field:
        refs.append((style2, None, [
            _('Description'),
            recombinant_language_text(field['description'])]))
    if 'obligation' in field:
        refs.append((style2, None, [
            _('Obligation'),
            recombinant_language_text(field['obligation'])]))
    if 'format_type' in field:
        refs.append((style2, None, [
            _('Format'),
            recombinant_language_text(field['format_type'])]))

def _append_field_choices_rows(refs, choices, count_range=None):
    label = _('Values')
    for key, value in choices:
        r = [label, unicode(key), value]
        if count_range: # used by _text choices validation
            r.extend([None]*6 + ['=SUMPRODUCT(--ISNUMBER(SEARCH('
                '","&B{n}&",",SUBSTITUTE(","&{r}&","," ",""))))'.format(
                    r=count_range,
                    n=len(refs) + 1)])
        refs.append((None, None, r))
        label = None

def _populate_reference_sheet(sheet, chromo, refs):
    for style, height, ref_line in refs:
        sheet.append(ref_line)
        if height:
            sheet.row_dimensions[sheet.max_row].height = height

        if not style:
            continue

        apply_styles(style, sheet.row_dimensions[sheet.max_row])
        for c in range(len(ref_line)):
            apply_styles(style, sheet.cell(
                row=sheet.max_row, column=c + 1))


def apply_styles(config, target):
    """
    apply styles from config to target

    currently supports PatternFill, Font, Alignment
    """
    pattern_fill = config.get('PatternFill')
    if pattern_fill:
        target.fill = openpyxl.styles.PatternFill(**pattern_fill)
    font = config.get('Font')
    if font:
        target.font = openpyxl.styles.Font(**font)
    alignment = config.get('Alignment')
    if alignment:
        target.alignment = openpyxl.styles.Alignment(**alignment)
