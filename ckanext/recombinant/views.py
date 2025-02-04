from flask import Blueprint, Response as FlaskResponse
from flask_babel import force_locale
import re
import simplejson as json
from sqlalchemy import text as sql_text

from typing import Union, Dict, Tuple, Any, Optional, List
from ckan.types import Response

from werkzeug.datastructures import FileStorage as FlaskFileStorage
from cgi import FieldStorage

from logging import getLogger

from ckan.plugins.toolkit import (
    _,
    g,
    h,
    asbool,
    abort,
    aslist,
    config,
    request,
    render
)

from ckan.logic import ValidationError, NotAuthorized
from ckan.model.group import Group
from ckan.authz import has_user_permission_for_group_or_org
from ckan.common import session

from ckan.views.dataset import _get_package_type

from ckanext.recombinant.errors import (
    RecombinantException,
    BadExcelData,
    format_trigger_error
)
from ckanext.recombinant.read_excel import read_excel, get_records
from ckanext.recombinant.write_excel import (
    excel_template,
    excel_data_dictionary,
    append_data
)
from ckanext.recombinant.tables import get_chromo, get_geno
from ckanext.recombinant.helpers import (
    recombinant_primary_key_fields, recombinant_choice_fields)

from io import BytesIO

# use import incase of ckan.datastore.sqlsearch.enabled = False
from ckanext.datastore.logic.action import datastore_search_sql
from ckanext.datastore.backend import DatastoreBackend
from ckanext.datastore.backend.postgres import (
    DatastorePostgresqlBackend,
    identifier as sql_identifier,
    _parse_constraint_error_from_psql_error
)

from ckanapi import NotFound, LocalCKAN


log = getLogger(__name__)
recombinant = Blueprint('recombinant', __name__)


@recombinant.route('/recombinant/upload/<id>', methods=['POST'])
def upload(id: str) -> Response:
    package_type = _get_package_type(id)
    geno = get_geno(package_type)
    lc = LocalCKAN(username=g.user)
    dataset = lc.action.package_show(id=id)
    org = lc.action.organization_show(id=dataset['owner_org'])
    dry_run = 'validate' in request.form
    # resource_name is only required for redirect,
    # so do not need to heavily validate that it exists in the geno.
    resource_name = request.form['resource_name']

    try:
        if not request.files['xls_update']:
            raise BadExcelData('You must provide a valid file')

        _process_upload_file(
            lc,
            dataset,
            request.files['xls_update'],
            geno,
            dry_run)

        if dry_run:
            h.flash_success(_(
                "No errors found."
                ))
        else:
            h.flash_success(_(
                "Your file was successfully uploaded into the central system."
                ))

        return h.redirect_to('recombinant.preview_table',
                             resource_name=resource_name,
                             owner_org=org['name'])
    except BadExcelData as e:
        h.flash_error(_(e.message))
        return h.redirect_to('recombinant.preview_table',
                             resource_name=resource_name,
                             owner_org=org['name'])


@recombinant.route('/recombinant/delete/<id>/<resource_id>', methods=['GET', 'POST'])
def delete_records(id: str, resource_id: str) -> Union[str, Response]:
    lc = LocalCKAN(username=g.user)
    filters = {}

    if not h.check_access('datastore_delete',
                          {'resource_id': resource_id,
                           'filters': filters}):
        return abort(403, _('User {0} not authorized to update resource {1}'.format(
            str(g.user), resource_id)))

    pkg = lc.action.package_show(id=id)
    res = lc.action.resource_show(id=resource_id)
    org = lc.action.organization_show(id=pkg['owner_org'])

    dataset = lc.action.recombinant_show(
        dataset_type=pkg['type'], owner_org=org['name'])

    def delete_error(err: str, _records: Optional[List[str]]) -> str:
        return render('recombinant/confirm_delete.html',
                      extra_vars={'dataset': dataset,
                                  'resource': res,
                                  'errors': [err],
                                  'num': len(_records),
                                  'bulk_delete': '\n'.join(
                                      _records
                                      # extra blank is needed to prevent field
                                      # from being completely empty
                                      + ([''] if '' in _records else []))})

    form_text = request.form.get('bulk-delete', '')
    if not form_text:
        # we can just silently refresh
        return h.redirect_to(
                'recombinant.preview_table',
                resource_name=res['name'],
                owner_org=org['name'])

    pk_fields = recombinant_primary_key_fields(res['name'])

    ok_records = []
    ok_filters = []
    records = iter(form_text.split('\n'))
    for r in records:
        r = r.rstrip('\r')

        def record_fail(err: str) -> str:
            # move bad record to the top of the pile
            filters['bulk-delete'] = '\n'.join(
                [r] + list(records) + ok_records)
            return delete_error(err, ok_records)

        split_on = '\t' if '\t' in r else ','
        fields = [f for f in r.split(split_on)]
        if len(fields) != len(pk_fields):
            return record_fail(_('Wrong number of fields, expected {num}').format(
                num=len(pk_fields)))

        filters.clear()
        for f, pkf in zip(fields, pk_fields):
            filters[pkf['datastore_id']] = f
        try:
            result = lc.action.datastore_search(
                resource_id=resource_id,
                filters=filters,
                limit=2)
        except ValidationError:
            return record_fail(_('Invalid fields'))
        found = result['records']
        if not found:
            return record_fail(_('No matching records found "%s"') %
                               '", "'.join(fields))
        if len(found) > 1:
            return record_fail(_('Multiple matching records found'))

        if r not in ok_records:
            ok_records.append(r)
            ok_filters.append(dict(filters))

    if 'cancel' in request.form:
        return h.redirect_to(
            'recombinant.preview_table',
            resource_name=res['name'],
            owner_org=org['name'])
    if 'confirm' not in request.form or request.method == 'GET':
        return render('recombinant/confirm_delete.html',
                      extra_vars={'dataset': dataset,
                                  'resource': res,
                                  'num': len(ok_records),
                                  'bulk_delete': '\n'.join(
                                      ok_records
                                      # extra blank is needed to prevent field
                                      # from being completely empty
                                      + ([''] if '' in ok_records else []))})
    if request.method == 'POST':
        for f in ok_filters:
            try:
                lc.action.datastore_delete(
                    resource_id=resource_id,
                    filters=f,
                    )
            except ValidationError as e:
                if 'constraint_info' in e.error_dict:
                    error_message = _render_recombinant_constraint_errors(
                        lc, e, get_chromo(res['name']), 'delete')
                    h.flash_error(error_message)
                    # type_ignore_reason: incomplete typing
                    return record_fail(error_message)  # type: ignore
                raise

        h.flash_success(_("{num} deleted.").format(num=len(ok_filters)))

    return h.redirect_to(
        'recombinant.preview_table',
        resource_name=res['name'],
        owner_org=org['name'],
        )


def _xlsx_response_headers() -> Tuple[str, str]:
    """
    Returns tuple of content type and disposition type.

    If the request is from MS Edge user agent, we force the XLSX
    download to prevent Edge from cowboying into Office Apps Online
    """
    content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    disposition_type = 'inline'
    user_agent_legacy = getattr(request, 'headers', {}).get('User-Agent')
    user_agent = getattr(request, 'headers', {}).get('Sec-CH-UA', user_agent_legacy)
    if user_agent and (
      "Microsoft Edge" in user_agent or
      "Edg/" in user_agent or
      "EdgA/" in user_agent):
        # force the XLSX file to be downloaded in MS Edge,
        # and not open in Office Apps Online.
        content_type = 'application/octet-stream'
        disposition_type = 'attachment'
    return content_type, disposition_type


@recombinant.route('/recombinant-template/<dataset_type>_<lang>_<owner_org>.xlsx',
                   methods=['GET', 'POST'])
def template(dataset_type: str, lang: str, owner_org: str) -> Response:
    """
    POST requests to this endpoint contain primary keys of
    records that are to be included in the excel file

    Parameters:
        bulk-template -> an array of strings, each string
        contains primary keys separated by commas

        resource_name -> the name of the resource containing the records
    """

    if lang != h.lang():
        return abort(404, _('Not found'))

    lc = LocalCKAN(username=g.user)
    try:
        dataset = lc.action.recombinant_show(
            dataset_type=dataset_type,
            owner_org=owner_org)
        org = lc.action.organization_show(
            id=owner_org,
            include_datasets=False)
    except NotFound:
        return abort(404, _('Not found'))

    try:
        book = excel_template(dataset_type, org)
    except RecombinantException as e:
        return abort(400, _('Unable to download template.\n%s') % e)

    if request.method == 'POST':
        filters = {}
        resource_name = request.form.get('resource_name', '')
        for r in dataset['resources']:
            if r['name'] == resource_name:
                resource = r
                break
        else:
            return abort(404, _("Resource not found"))

        pk_fields = recombinant_primary_key_fields(resource['name'])
        primary_keys = request.form.getlist('bulk-template')
        chromo = get_chromo(resource['name'])
        record_data = []

        for keys in primary_keys:
            temp = keys.split(",")
            for f, pkf in zip(temp, pk_fields):
                filters[pkf['datastore_id']] = f
            try:
                result = lc.action.datastore_search(resource_id=resource['id'],
                                                    filters=filters)
            except NotAuthorized:
                return abort(403, _('Unauthorized to read resource %s') %
                             resource['id'])
            record_data += result['records']

        append_data(book, record_data, chromo)

        resource_names = dict((r['id'], r['name']) for r in dataset['resources'])
        ds_info = lc.action.datastore_info(id=resource['id'])
        if 'foreignkeys' in ds_info['meta']:
            for fk in ds_info['meta']['foreignkeys']:
                f_chromo = None
                foreign_constraints_sql = None
                if resource['id'] == fk['child_table']:
                    f_chromo = get_chromo(resource_names[fk['parent_table']])
                    foreign_constraints_sql = sql_text('''
                        SELECT parent.* FROM {0} parent
                        JOIN {1} child ON {2}
                        ORDER BY parent._id
                    '''.format(sql_identifier(fk['parent_table']),
                               sql_identifier(fk['child_table']),
                               ' AND '.join(
                                   ['parent.{0} = child.{1}'.format(
                                       fk_c, fk['child_columns'][fk_i])
                                   for fk_i, fk_c in enumerate(
                                       fk['parent_columns'])])))
                elif resource['id'] == fk['parent_table']:
                    f_chromo = get_chromo(resource_names[fk['child_table']])
                    foreign_constraints_sql = sql_text('''
                        SELECT child.* FROM {0} child
                        JOIN {1} parent ON {2}
                        ORDER BY child._id
                    '''.format(sql_identifier(fk['child_table']),
                               sql_identifier(fk['parent_table']),
                               ' AND '.join(
                                   ['child.{0} = parent.{1}'.format(
                                       fk_c, fk['parent_columns'][fk_i])
                                   for fk_i, fk_c in enumerate(
                                       fk['child_columns'])])))
                if foreign_constraints_sql is not None and f_chromo is not None:
                    results = datastore_search_sql(
                        {'ignore_auth': True}, {'sql': str(foreign_constraints_sql)})
                    if results:
                        append_data(book, results['records'], f_chromo)

    blob = BytesIO()
    book.save(blob)
    response = FlaskResponse(blob.getvalue())
    content_type, disposition_type = _xlsx_response_headers()
    response.headers['Content-Type'] = content_type
    response.headers['Content-Disposition'] = (
        '{}; filename="{}_{}_{}.xlsx"'.format(
            disposition_type,
            dataset['owner_org'],
            lang,
            dataset['dataset_type']))
    return response


def _data_dictionary(dataset_type: str,
                     published_resource: bool = False) -> Response:
    try:
        geno = get_geno(dataset_type)
    except RecombinantException:
        return abort(404, _('Recombinant dataset_type not found'))

    book = excel_data_dictionary(geno, published_resource=published_resource)
    blob = BytesIO()
    book.save(blob)
    response = FlaskResponse(blob.getvalue())
    content_type, disposition_type = _xlsx_response_headers()
    response.headers['Content-Type'] = content_type
    response.headers['Content-Disposition'] = '{}; filename="{}.xlsx"'.format(
        disposition_type,
        dataset_type)
    return response


@recombinant.route('/recombinant-dictionary/<dataset_type>')
def data_dictionary(dataset_type: str) -> Response:
    return _data_dictionary(dataset_type, published_resource=False)


@recombinant.route('/recombinant-published-dictionary/<dataset_type>')
def published_data_dictionary(dataset_type: str) -> Response:
    return _data_dictionary(dataset_type, published_resource=True)


def _schema_json(dataset_type: str, published_resource: bool = False) -> Response:
    try:
        geno = get_geno(dataset_type)
    except RecombinantException:
        return abort(404, _('Recombinant dataset_type not found'))

    schema = {}
    schema['dataset_type'] = geno['dataset_type']
    schema['title'] = {}
    schema['notes'] = {}

    _locales_offered = config.get('ckan.locales_offered', ['en'])
    if not isinstance(_locales_offered, list):
        _locales_offered = _locales_offered.split()

    for lang in _locales_offered:
        with force_locale(lang):
            schema['title'][lang] = _(geno['title'])
            schema['notes'][lang] = _(geno['notes'])

    if 'front_matter' in geno:
        schema['front_matter'] = {}
        for lang in sorted(geno['front_matter']):
            schema['front_matter'][lang] = geno['front_matter'][lang]

    schema['resources'] = []
    for chromo in geno['resources']:
        resource = {}
        schema['resources'].append(resource)
        choice_fields = recombinant_choice_fields(
            chromo['resource_name'],
            all_languages=True)

        pkeys = aslist(chromo['datastore_primary_key'])

        resource['resource_name'] = chromo['resource_name']
        resource['title'] = {}
        for lang in _locales_offered:
            with force_locale(lang):
                resource['title'][lang] = _(chromo['title'])

        if not published_resource:
            resource['primary_key'] = pkeys

        resource['fields'] = []
        for field in chromo['fields']:
            if not field.get('visible_to_public', True):
                continue
            if not published_resource and field.get(
              'published_resource_computed_field', False):
                continue
            fld = {}
            resource['fields'].append(fld)
            fld['id'] = field['datastore_id']
            if field.get('max_chars'):
                fld['character_limit'] = field['max_chars']
            fld['obligation'] = {}
            for lang in _locales_offered:
                with force_locale(lang):
                    if fld['id'] in pkeys:
                        fld['obligation'][lang] = _('Mandatory')
                    elif field.get('excel_required'):
                        fld['obligation'][lang] = _('Mandatory')
                    elif field.get('excel_required_formula'):
                        fld['obligation'][lang] = _('Conditional')
                    else:
                        fld['obligation'][lang] = _('Optional')
            for k in ['label', 'description', 'validation', 'obligation']:
                if k in field:
                    if isinstance(field[k], dict):
                        fld[k] = field[k]
                        continue
                    fld[k] = {}
                    for lang in _locales_offered:
                        with force_locale(lang):
                            fld[k][lang] = _(field[k])

            fld['datastore_type'] = field['datastore_type']

            if fld['id'] in choice_fields:
                choices = {}
                fld['choices'] = choices
                for ck, cv in choice_fields[fld['id']]:
                    choices[ck] = cv

        if not published_resource and 'examples' in chromo:
            ex_record = chromo['examples']['record']
            example = {}
            for field in chromo['fields']:
                if field['datastore_id'] in ex_record:
                    example[field['datastore_id']] = ex_record[
                        field['datastore_id']]
            resource['example_record'] = example

    response = Response(json.dumps(schema,
                                   indent=2,
                                   ensure_ascii=False).encode('utf-8'))
    response.headers['Content-Type'] = 'application/json'
    response.headers['Content-Disposition'] = (
        'inline; filename="{0}.json"'.format(
            dataset_type))
    return response


@recombinant.route('/recombinant-schema/<dataset_type>.json')
def schema_json(dataset_type: str) -> Response:
    return _schema_json(dataset_type, published_resource=False)


@recombinant.route('/recombinant-published-schema/<dataset_type>.json')
def published_schema_json(dataset_type: str) -> Response:
    return _schema_json(dataset_type, published_resource=True)


@recombinant.route('/recombinant/<resource_name>')
def type_redirect(resource_name: str) -> Response:
    orgs = h.organizations_available('read')

    if not orgs:
        return abort(404, _('No organizations found'))
    try:
        get_chromo(resource_name)
    except RecombinantException:
        return abort(404, _('Recombinant resource_name not found'))

    return h.redirect_to(
        'recombinant.preview_table',
        resource_name=resource_name,
        owner_org=orgs[0]['name'],
    )


def dataset_redirect(package_type: str, id: str) -> Response:
    lc = LocalCKAN(username=g.user)
    dataset = lc.action.package_show(id=id)
    return h.redirect_to(
        'recombinant.preview_table',
        resource_name=package_type,
        owner_org=dataset['organization']['name'],
    )


def resource_redirect(package_type: str, id: str, resource_id: str) -> Response:
    return dataset_redirect(package_type, id)


@recombinant.route('/recombinant/<resource_name>/<owner_org>', methods=['GET', 'POST'])
def preview_table(resource_name: str,
                  owner_org: str) -> Union[str, Response]:
    if not g.user:
        return h.redirect_to('user.login')

    org_object = Group.get(owner_org)
    if not org_object:
        return abort(404, _('Organization not found'))
    if org_object.name != owner_org:
        return h.redirect_to(
            'recombinant.preview_table',
            resource_name=resource_name,
            owner_org=org_object.name,
        )

    lc = LocalCKAN(username=g.user, context={'ignore_auth': True})
    try:
        chromo = get_chromo(resource_name)
    except RecombinantException:
        return abort(404, _('Recombinant resource_name not found'))

    if 'create' in request.form or 'refresh' in request.form:
        # check if the user can update datasets for organization
        # admin and editors should be able to init recombinant records
        if not has_user_permission_for_group_or_org(org_object.id,
                                                    g.user,
                                                    'update_dataset'):
            return abort(403, _('User %s not authorized to create packages') %
                         (str(g.user)))
        try:
            # check if the dataset exists
            dataset = lc.action.recombinant_show(
                dataset_type=chromo['dataset_type'], owner_org=owner_org)
            # check that the resource has errors
            for _r in dataset['resources']:
                if _r['name'] == resource_name and 'error' in _r:
                    raise NotFound
        except NotFound:
            try:
                if 'create' in request.form:
                    lc.action.recombinant_create(
                        dataset_type=chromo['dataset_type'], owner_org=owner_org)
                else:
                    lc.action.recombinant_update(
                        dataset_type=chromo['dataset_type'], owner_org=owner_org,
                        force_update=True)
            except NotAuthorized as e:
                return abort(403, e.message or '')
        return h.redirect_to(
            'recombinant.preview_table',
            resource_name=resource_name,
            owner_org=owner_org,
            )

    try:
        dataset = lc.action.recombinant_show(
            dataset_type=chromo['dataset_type'], owner_org=owner_org)
    except NotFound:
        dataset = None
    org = lc.action.organization_show(id=owner_org)

    if dataset:
        for r in dataset['resources']:
            if r['name'] == resource_name:
                break
        else:
            return abort(404, _('Resource not found'))
    else:
        r = None

    return render('recombinant/resource_edit.html', extra_vars={
        'dataset': dataset,
        'dataset_type': chromo['dataset_type'],
        'resource_description': chromo['title'],
        'resource_name': chromo['resource_name'],
        'resource': r,
        'organization': org,
        'errors': None,
        'delete_errors': None,
        'filters': None
        })


def _process_upload_file(lc: LocalCKAN,
                         dataset: Dict[str, Any],
                         upload_file: Union[str, FlaskFileStorage, FieldStorage],
                         geno: Dict[str, Any],
                         dry_run: bool):
    """
    Use lc.action.datastore_upsert to load data from upload_file

    raises BadExcelData on errors.

    NOTE (2024-09-20): All sheets in an XLSX file need to pass validation
                       to be successfully committed to the database.
    """
    owner_org = dataset['organization']['name']

    expected_sheet_names = dict(
        (resource['name'], resource['id'])
        for resource in dataset['resources'])

    upload_data = read_excel(upload_file)
    total_records = 0
    # type_ignore_reason: incomplete typing
    backend: DatastorePostgresqlBackend = DatastoreBackend.\
        get_active_backend()  # type: ignore
    ds_write_connection = backend._get_write_engine().connect()
    ds_write_transaction = ds_write_connection.begin()
    try:
        while True:
            try:
                sheet_name, org_name, column_names, rows = next(upload_data)
            except StopIteration:
                break
            except BadExcelData as e:
                raise e
            except Exception:
                # unfortunately this can fail in all sorts of ways
                if asbool(config.get('debug', False)):
                    # on debug we want the real error
                    raise
                raise BadExcelData(
                    _("The server encountered a problem processing the file "
                      "uploaded. Please try copying your data into the latest "
                      "version of the template and uploading again. If this "
                      "problem continues, send your Excel file to "
                      "open-ouvert@tbs-sct.gc.ca so we may investigate."))

            if sheet_name not in expected_sheet_names:
                raise BadExcelData(_('Invalid file for this data type. ' +
                                     'Sheet must be labeled "{0}", ' +
                                     'but you supplied a sheet labeled "{1}"').format(
                                        '"/"'.join(sorted(expected_sheet_names)),
                                        sheet_name))

            if not h.check_access('datastore_upsert',
                                  {'resource_id': expected_sheet_names[sheet_name]}):
                return abort(403, _('User {0} not authorized to update resource {1}'
                                    .format(str(g.user),
                                            expected_sheet_names[sheet_name])))

            if org_name != owner_org:
                raise BadExcelData(_(
                    'Invalid sheet for this organization. ' +
                    'Sheet must be labeled for {0}, ' +
                    'but you supplied a sheet for {1}').format(
                        owner_org, org_name))

            # custom styles or other errors cause columns to be read
            # that actually have no data. strip them here to avoid error below
            while column_names and column_names[-1] is None:
                column_names.pop()

            chromo = get_chromo(sheet_name)
            expected_columns = [f['datastore_id'] for f in chromo['fields']
                                if f.get('import_template_include', True) and
                                not f.get('published_resource_computed_field')]
            if column_names != expected_columns:
                raise BadExcelData(
                    _("This template is out of date. "
                      "Please try copying your data into the latest "
                      "version of the template and uploading again. If this "
                      "problem continues, send your Excel file to "
                      "open-ouvert@tbs-sct.gc.ca so we may investigate."))

            pk = chromo.get('datastore_primary_key', [])
            choice_fields = {
                f['datastore_id']:
                    'full' if f.get('excel_full_text_choices') else True
                for f in chromo['fields']
                if ('choices' in f or 'choices_file' in f)}

            records = get_records(
                rows,
                [f for f in chromo['fields'] if f.get(
                    'import_template_include', True) and not f.get(
                        'published_resource_computed_field')],
                pk,
                choice_fields)
            method = 'upsert' if pk else 'insert'
            total_records += len(records)
            if not records:
                continue
            try:
                lc.call_action('datastore_upsert', data_dict=dict(
                        method=method,
                        resource_id=expected_sheet_names[sheet_name],
                        records=[r[1] for r in records],
                        dry_run=dry_run),
                    context={'connection': ds_write_connection}
                )
            except ValidationError as e:
                if 'constraint_info' in e.error_dict:
                    # type_ignore_reason: incomplete typing
                    pgerror = e.error_dict['errors'][
                        'foreign_constraint'][0]  # type: ignore
                elif 'info' in e.error_dict:
                    # because, where else would you put the error text?
                    # XXX improve this in datastore, please
                    # type_ignore_reason: incomplete typing
                    pgerror = e.error_dict['info']['orig'][0].decode(  # type: ignore
                        'utf-8')
                else:
                    # type_ignore_reason: incomplete typing
                    pgerror = e.error_dict['records'][0]  # type: ignore
                if isinstance(pgerror, dict):
                    pgerror = '; '.join(
                        (h.recombinant_language_text(
                            h.recombinant_get_field(sheet_name, k)['label']) if
                            h.recombinant_get_field(sheet_name, k) else k) + _(':')
                        + ' ' + ', '.join(format_trigger_error(v))
                        for k, v in pgerror.items())
                else:
                    # remove some postgres-isms that won't help the user
                    # when we render this as an error in the form
                    pgerror = re.sub(r'\nLINE \d+:', '', pgerror)
                    pgerror = re.sub(r'\n *\^\n$', '', pgerror)
                if 'records_row' in e.error_dict:
                    if 'constraint_info' in e.error_dict:
                        pgerror = _render_recombinant_constraint_errors(
                            lc, e, chromo, 'upsert')
                    elif 'invalid input syntax for type integer' in pgerror:
                        if ':' in pgerror:
                            pgerror = _('Invalid input syntax for type integer: {}')\
                                .format(pgerror.split(':')[1].strip())
                        else:
                            pgerror = _('Invalid input syntax for type integer')
                    raise BadExcelData(
                        _('Sheet {0} Row {1}:').format(
                            sheet_name,
                            # type_ignore_reason: incomplete typing
                            records[e.error_dict['records_row']][0])  # type: ignore
                        + ' '
                        + pgerror)
                raise BadExcelData(
                    _("Error while importing data: {0}").format(
                        pgerror))
        if not total_records:
            raise BadExcelData(_("The template uploaded is empty"))
        if dry_run:
            ds_write_transaction.rollback()
        else:
            ds_write_transaction.commit()
    except Exception:
        ds_write_transaction.rollback()
        raise
    finally:
        ds_write_connection.close()


def _render_recombinant_constraint_errors(lc: LocalCKAN,
                                          exception: Exception,
                                          chromo: Dict[str, Any],
                                          action: str) -> str:
    # type_ignore_reason: incomplete typing
    orig_errmsg = exception.error_dict['errors'][
        'foreign_constraint'][0]  # type: ignore
    foreign_error = chromo.get(
        'datastore_constraint_errors', {}).get(action)
    fk_err_template = chromo.get(
        'datastore_constraint_error_templates', {}).get(action)
    if foreign_error and not fk_err_template:
        # type_ignore_reason: incomplete typing
        error_message = _parse_constraint_error_from_psql_error(
            exception, foreign_error)['errors'][
                'foreign_constraint'][0]  # type: ignore
    elif fk_err_template:
        ref_res_dict = lc.action.resource_show(
            id=exception.error_dict['constraint_info']['ref_resource'])
        ref_pkg_dict = lc.action.package_show(
            id=ref_res_dict['package_id'])
        dt_query = {}
        _ref_keys = exception.error_dict['constraint_info'][
            'ref_keys'].replace(' ', '').split(',')
        _ref_values = exception.error_dict['constraint_info'][
            'ref_values'].replace(' ', '').split(',')
        for _i, key in enumerate(_ref_keys):
            dt_query[key] = _ref_values[_i]
        dt_query = json.dumps(dt_query, separators=(',', ':'))
        error_message = render(fk_err_template,
                               extra_vars=dict(
                                   exception.error_dict['constraint_info'],
                                   ref_resource=ref_res_dict,
                                   ref_dataset=ref_pkg_dict,
                                   dt_query=dt_query))
    else:
        error_message = orig_errmsg
    return error_message
