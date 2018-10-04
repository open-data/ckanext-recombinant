import openpyxl

from ckanext.recombinant.tables import get_geno
from ckanext.recombinant.errors import RecombinantException
from ckanext.recombinant.datatypes import datastore_type
from ckanext.recombinant.helpers import (
    recombinant_choice_fields, recombinant_language_text)

from ckan.plugins.toolkit import _

white_font = openpyxl.styles.Font(color=openpyxl.styles.colors.WHITE)

HEADER_ROW, HEADER_HEIGHT = 1, 27
CHEADINGS_ROW, CHEADINGS_HEIGHT = 2, 22
LINE_HEIGHT = 15  # extra lines of text in same cell
CODE_ROW = 3
CSTATUS_ROW, CSTATUS_HEIGHT = 4, 6
EXAMPLE_ROW, EXAMPLE_HEIGHT = 5, 15
EXAMPLE_MERGE = 'A5:B5'
FREEZE_PANES = 'C5'
DATA_FIRST_ROW, DATA_HEIGHT = 6, 24
DATA_NUM_ROWS = 10000
RSTATUS_COL, RSTATUS_WIDTH = 'A', 0.6
RPAD_COL, RPAD_WIDTH = 'B', 2.3
DATA_FIRST_COL, DATA_FIRST_COL_NUM = 'C', 3
ESTIMATE_WIDTH_MULTIPLE = 1.1
EDGE_RANGE = 'A1:A4' # just to look spiffy
PAD_RANGE = 'B1:B4'

REF_HEADER1_ROW, REF_HEADER1_HEIGHT = 1, 27
REF_HEADER2_ROW, REF_HEADER2_HEIGHT = 2, 27
REF_FIRST_ROW = 4
REF_FIELD_NUM_COL_NUM = 1
REF_FIELD_NUM_MERGE = 'A{row}:B{row}'
REF_FIELD_TITLE_HEIGHT = 24
REF_FIELD_TITLE_COL_NUM = 3
REF_KEY_COL_NUM = 3
REF_KEY_WIDTH = 18
REF_VALUE_WIDTH = 114
REF_EDGE_RANGE = 'A1:A2'
REF_PAD_RANGE = 'B1:B2'

def excel_template(dataset_type, org):
    """
    return an openpyxl.Workbook object containing the sheet and header fields
    for passed dataset_type and org. Supports version 2 and 3 templates.
    """
    geno = get_geno(dataset_type)
    version = geno.get('template_version', 2)

    book = openpyxl.Workbook()
    sheet = book.active
    refs = []
    for rnum, chromo in enumerate(geno['resources'], 1):
        if version == 2:
            _populate_excel_sheet_v2(sheet, chromo, org, refs)
        elif version == 3:
            _populate_excel_sheet(sheet, chromo, org, refs, rnum)
        sheet = book.create_sheet()

    if version == 2:
        _populate_reference_sheet_v2(sheet, chromo, refs)
    elif version == 3:
        _populate_reference_sheet(sheet, chromo, refs)
    sheet.title = 'reference'

    if version == 2:
        return book

    for i, chromo in enumerate(geno['resources']):
        sheet = book.create_sheet()
        _populate_excel_validation(sheet, chromo, org, refs)
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
                    choice_fields[field['datastore_id']],
                    style2)

        _populate_reference_sheet(sheet, chromo, refs)
        sheet = None

    return book


def estimate_width(text):
    return max(len(s) for s in text.split('\n')) * ESTIMATE_WIDTH_MULTIPLE


def _populate_excel_sheet(sheet, chromo, org, refs, resource_num):
    """
    Format openpyxl sheet for the resource definition chromo and org.
    (Version 3)

    refs - list of rows to add to reference sheet, modified
        in place from this function
    resource_num - 1-based index of resource
    """
    sheet.title = chromo['resource_name']

    def fill_cell(row, column, value, styles):
        c = sheet.cell(row=row, column=column)
        c.value = value
        apply_styles(styles, c)

    edge_style = chromo.get('excel_edge_style', {
        'PatternFill': {
            'patternType': 'solid',
            'fgColor': 'FFFFF056'},
        'Font': {
            'bold': True}})
    required_style = chromo.get('excel_required_style', edge_style)
    header_style = chromo.get('excel_header_style', {
        'PatternFill': {
            'patternType': 'solid',
            'fgColor': 'FFDFE2DB'},
        'Font': {
            'size': 16}})
    cheading_style = chromo.get('excel_column_heading_style', {
        'PatternFill': {
            'patternType': 'solid',
            'fgColor': 'FFDFE2DB'},
        'Font': {
            'underline': 'single'},
        'Alignment': {
            'vertical': 'bottom'}})
    example_style = chromo.get('excel_example_style', {
        'PatternFill': {
            'patternType': 'solid',
            'fgColor': 'FFDDD9C4'}})
    errors_style = chromo.get('excel_error_style', {
        'PatternFill': {
            'patternType': 'solid',
            'fgColor': 'FFC00000'},
        'Font': {
            'color': 'FFFFFF'}})

    sheet.row_dimensions[HEADER_ROW].height = HEADER_HEIGHT
    cheadings_dimensions = sheet.row_dimensions[CHEADINGS_ROW]
    cheadings_dimensions.height = CHEADINGS_HEIGHT
    sheet.row_dimensions[CODE_ROW].hidden = True
    sheet.row_dimensions[CSTATUS_ROW].height = CSTATUS_HEIGHT
    sheet.row_dimensions[EXAMPLE_ROW].height = EXAMPLE_HEIGHT
    for i in xrange(DATA_FIRST_ROW, DATA_FIRST_ROW + DATA_NUM_ROWS):
        sheet.row_dimensions[i].height = DATA_HEIGHT

    sheet.column_dimensions[RSTATUS_COL].width = RSTATUS_WIDTH
    sheet.column_dimensions[RPAD_COL].width = RPAD_WIDTH

    sheet.freeze_panes = sheet[FREEZE_PANES]

    apply_styles(header_style, sheet.row_dimensions[HEADER_ROW])
    apply_styles(cheading_style, sheet.row_dimensions[CHEADINGS_ROW])
    apply_styles(cheading_style, sheet.row_dimensions[CSTATUS_ROW])
    apply_styles(example_style, sheet.row_dimensions[EXAMPLE_ROW])
    for c in sheet[EDGE_RANGE]:
        apply_styles(edge_style, c)

    sheet.merge_cells(EXAMPLE_MERGE)
    fill_cell(EXAMPLE_ROW, 1, _('e.g.'), example_style)

    fill_cell(
        HEADER_ROW,
        DATA_FIRST_COL_NUM,
        recombinant_language_text(chromo['title']) + '        ' + org['title'],
        header_style)

    sheet.cell(CODE_ROW, 1).value = 'v3'  # template version
    sheet.cell(CODE_ROW, 2).value = org['name']  # allow only upload to this org

    choice_fields = dict(
        (f['datastore_id'], f['choices'])
        for f in recombinant_choice_fields(chromo['resource_name']))

    for col_num, field in enumerate(
            (f for f in chromo['fields'] if f.get(
                'import_template_include', True)), DATA_FIRST_COL_NUM):
        field_heading = recombinant_language_text(
            field.get('excel_heading', field['label']))
        cheadings_dimensions.height = max(
            cheadings_dimensions.height,
            field_heading.count('\n') * LINE_HEIGHT + CHEADINGS_HEIGHT)
        fill_cell(
            CHEADINGS_ROW,
            col_num,
            field_heading,
            cheadings_style)
        sheet.cell(CHEADINGS_ROW, n).hyperlink = 'reference!${col}${row}'.format(
            col=openpyxl.cell.get_column_letter(REF_KEY_COL_NUM),
            row=len(refs) + 2)
        col = sheet.column_dimensions[col_letter]
        if 'excel_column_width' in field:
            col.width = field['excel_column_width']
        else:
            col.width = estimate_width(field_heading)

        sheet.cell(CODE_ROW, n).value = field['datastore_id']  # match against db columns
        # jumping through openpyxl hoops:
        col_letter = openpyxl.cell.get_column_letter(col_num)
        col_letter_before = openpyxl.cell.get_column_letter(max(1, col_num-1))
        col_letter_after = openpyxl.cell.get_column_letter(col_num+1)

        validation_range = '{col}{row1}:{col}{rowN}'.format(
            col=col_letter,
            row1=DATA_FIRST_ROW,
            rowN=DATA_FIRST_ROW + DATA_NUM_ROWS - 1)

        xl_format = datastore_type[field['datastore_type']].xl_format
        alignment = openpyxl.styles.Alignment(wrap_text=True)
        protection = openpyxl.styles.Protection(locked=False)
        for c in worksheet[validation_range]:
            c.number_format = xl_format
            c.alignment = alignment
            c.protection = protection

        _append_field_ref_rows(refs, field, link)

        if field['datastore_id'] in choice_fields:
            ref1 = len(refs) + 2
            _append_field_choices_rows(
                refs,
                choice_fields[field['datastore_id']])
            refN = len(refs)

            choice_range = 'reference!${col}${ref1}:${col}${refN}'.format(
                col=REF_KEY_COL_NUM, ref1=ref1, refN=refN)

            choices = [c[0] for c in choice_fields[field['datastore_id']]]
            if field['datastore_type'] != '_text':
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


def _populate_excel_sheet_v2(sheet, chromo, org, refs):
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
    required_color = chromo.get('excel_required_border_color', '763626')

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
        col_letter_before = openpyxl.cell.get_column_letter(max(1, n-1))
        col_letter_after = openpyxl.cell.get_column_letter(n+1)
        col = sheet.column_dimensions[col_letter]
        col.width = field['excel_column_width']
        col.alignment = openpyxl.styles.Alignment(
            wrap_text=True)
        # FIXME: format only below header
        col.number_format = datastore_type[field['datastore_type']].xl_format
        validation_range = '{0}4:{0}1004'.format(col_letter)

        _append_field_ref_rows_v2(refs, field, org_style, header_style)

        if field['datastore_type'] == 'boolean':
            boolean_validator.ranges.append(validation_range)
        if field['datastore_type'] == 'date':
            sheet.conditional_formatting.add(validation_range,
                openpyxl.formatting.FormulaRule([
                        # +0 is needed by excel to recognize dates. sometimes.
                        'AND(NOT(ISBLANK({cell})),NOT(ISNUMBER({cell}+0)))'
                        .format(cell=col_letter + '4',)],
                    stopIfTrue=True,
                    fill=error_fill,
                    font=white_font,
                    ))
            sheet.conditional_formatting.add("{0}2".format(col_letter),
                openpyxl.formatting.FormulaRule([
                        # +0 is needed by excel to recognize dates. sometimes.
                        'SUMPRODUCT(--NOT(ISBLANK({cells})),'
                        '--NOT(ISNUMBER({cells}+0)))'
                        .format(cells=validation_range,)],
                    stopIfTrue=True,
                    fill=error_fill,
                    font=white_font,
                    ))
        if field['datastore_type'] == 'int':
            sheet.conditional_formatting.add(validation_range,
                openpyxl.formatting.FormulaRule([
                        'AND(NOT(ISBLANK({cell})),NOT(IFERROR(INT({cell})={cell},FALSE)))'
                        .format(cell=col_letter + '4',)],
                    stopIfTrue=True,
                    fill=error_fill,
                    font=white_font,
                    ))
            sheet.conditional_formatting.add("{0}2".format(col_letter),
                openpyxl.formatting.FormulaRule([
                        'SUMPRODUCT(--NOT(ISBLANK({cells})),'
                        '--NOT(IFERROR(INT({cells})={cells},FALSE)))'
                        .format(cells=validation_range,)],
                    stopIfTrue=True,
                    fill=error_fill,
                    font=white_font,
                    ))
        if field['datastore_type'] == 'money':
            sheet.conditional_formatting.add(validation_range,
                openpyxl.formatting.FormulaRule([
                        # isblank doesnt work. sometimes. trim()="" is more permissive
                        'AND(NOT(TRIM({cell})=""),NOT(IFERROR(ROUND({cell},2)={cell},FALSE)))'
                        .format(cell=col_letter + '4',)],
                    stopIfTrue=True,
                    fill=error_fill,
                    font=white_font,
                    ))
            sheet.conditional_formatting.add("{0}2".format(col_letter),
                openpyxl.formatting.FormulaRule([
                        # isblank doesnt work. sometimes. trim()="" is more permissive
                        'SUMPRODUCT(--NOT(TRIM({cells})=""),'
                        '--NOT(IFERROR(ROUND({cells},2)={cells},FALSE)))'
                        .format(cells=validation_range,)],
                    stopIfTrue=True,
                    fill=error_fill,
                    font=white_font,
                    ))


        if field['datastore_id'] in choice_fields:
            ref1 = len(refs) + 1
            _append_field_choices_rows_v2(
                refs,
                choice_fields[field['datastore_id']],
                header_style,
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
                            'SUMPRODUCT(--NOT(TRIM({0})=""))'
                            '-SUMPRODUCT(COUNTIF({1},TRIM({0})))'
                            .format(validation_range, choice_range))],
                        stopIfTrue=True,
                        fill=error_fill,
                        font=white_font,
                        ))

        if field.get('excel_cell_required_formula'):
            sheet.conditional_formatting.add(validation_range,
                openpyxl.formatting.FormulaRule([
                        field['excel_cell_required_formula'].format(
                            column=col_letter,
                            column_before=col_letter_before,
                            column_after=col_letter_after,
                            row='4',
                        )],
                    stopIfTrue=True,
                    border=required_border,
                    ))
        elif (field.get('excel_required') or
                field['datastore_id'] in chromo['datastore_primary_key']):
            # hilight missing values
            sheet.conditional_formatting.add(validation_range,
                openpyxl.formatting.FormulaRule([(
                        'AND({col}4="",SUMPRODUCT(LEN(A4:Z4)))'
                        .format(col=col_letter)
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


def _append_field_ref_rows(refs, field, link):
    refs.append((None, []))
    refs.append(('title', link, [
        recombinant_language_text(field['label'])]))
    refs.append(('attr', None, [
        _('ID'),
        field['datastore_id']]))
    if 'description' in field:
        refs.append(('attr', None, [
            _('Description'),
            recombinant_language_text(field['description'])]))
    if 'obligation' in field:
        refs.append(('attr', None, [
            _('Obligation'),
            recombinant_language_text(field['obligation'])]))
    if 'format_type' in field:
        refs.append(('attr', None, [
            _('Format'),
            recombinant_language_text(field['format_type'])]))


def _append_field_ref_rows_v2(refs, field, style1, style2):
    a1 = (style2, style1, 24)
    a2 = (style2, None, None)
    refs.append((None, []))
    refs.append((a1, [
        _('Field Name'),
        recombinant_language_text(field['label'])]))
    refs.append((a2, [
        _('ID'),
        field['datastore_id']]))
    if 'description' in field:
        refs.append((a2, [
            _('Description'),
            recombinant_language_text(field['description'])]))
    if 'obligation' in field:
        refs.append((a2, [
            _('Obligation'),
            recombinant_language_text(field['obligation'])]))
    if 'format_type' in field:
        refs.append((a2, [
            _('Format'),
            recombinant_language_text(field['format_type'])]))

def _append_field_choices_rows(refs, choices):
    refs.append(('attr', [_('Values')]))
    for key, value in choices:
        refs.append(('choice', [unicode(key), value]))

def _append_field_choices_rows_v2(refs, choices, style2, count_range=None):
    label = _('Values')
    a1 = (style2, None, 24)
    for key, value in choices:
        r = [label, unicode(key), value]
        if count_range: # used by _text choices validation
            r.extend([None]*6 + ['=SUMPRODUCT(--ISNUMBER(SEARCH('
                '","&B{n}&",",SUBSTITUTE(","&{r}&","," ",""))))'.format(
                    r=count_range,
                    n=len(refs) + 1)])
        refs.append((a1, r))
        label = None
        a1 = (style2, None, None)

def _populate_reference_sheet(sheet, chromo, refs):
    for style, ref_line in refs:
        sheet.append(ref_line)
        if not style:
            continue

        s1, s2, height = style
        if height:
            sheet.row_dimensions[sheet.max_row].height = height

        if s2:
            apply_styles(s2, sheet.row_dimensions[sheet.max_row])
        for c in range(len(ref_line)):
            if c and s2:
                apply_styles(s2, sheet.cell(
                    row=sheet.max_row, column=c + 1))
            if not c and s1:
                apply_styles(s1, sheet.cell(
                    row=sheet.max_row, column=c + 1))

def _populate_reference_sheet_v2(sheet, chromo, refs):
    for style, ref_line in refs:
        sheet.append(ref_line)
        if not style:
            continue

        s1, s2, height = style
        if height:
            sheet.row_dimensions[sheet.max_row].height = height

        if s2:
            apply_styles(s2, sheet.row_dimensions[sheet.max_row])
        for c in range(len(ref_line)):
            if c and s2:
                apply_styles(s2, sheet.cell(
                    row=sheet.max_row, column=c + 1))
            if not c and s1:
                apply_styles(s1, sheet.cell(
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
