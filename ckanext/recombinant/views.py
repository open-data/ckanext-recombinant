from flask import Blueprint, Response
import re
from collections import OrderedDict
import simplejson as json

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

from ckan.views.dataset import _get_package_type

from ckanext.recombinant.errors import RecombinantException, BadExcelData
from ckanext.recombinant.read_excel import read_excel, get_records
from ckanext.recombinant.write_excel import (
    excel_template, excel_data_dictionary, append_data)
from ckanext.recombinant.tables import get_chromo, get_geno
from ckanext.recombinant.helpers import (
    recombinant_primary_key_fields, recombinant_choice_fields)

from cStringIO import StringIO

log = getLogger(__name__)

import ckanapi


recombinant = Blueprint('recombinant', __name__)


@recombinant.route('/recombinant/upload/<id>', methods=['POST'])
def upload(id):
    package_type = _get_package_type(id)
    geno = get_geno(package_type)
    lc = ckanapi.LocalCKAN(username=g.user)
    dataset = lc.action.package_show(id=id)
    org = lc.action.organization_show(id=dataset['owner_org'])
    dry_run = 'validate' in request.form
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
                             resource_name=dataset['resources'][0]['name'],
                             owner_org=org['name'])
    except BadExcelData as e:
        h.flash_error(_(e.message))
        return h.redirect_to('recombinant.preview_table',
                             resource_name=dataset['resources'][0]['name'],
                             owner_org=org['name'])

@recombinant.route('/recombinant/delete/<id>/<resource_id>', methods=['POST'])
def delete_records(id, resource_id):
    lc = ckanapi.LocalCKAN(username=g.user)
    filters = {}

    if not h.check_access('datastore_delete', {'resource_id': resource_id, 'filters': filters}):
        abort(403, _('User {0} not authorized to update resource {1}'
                    .format(str(g.user), resource_id)))

    x_vars = {'filters': filters, 'action': 'edit'}
    pkg = lc.action.package_show(id=id)
    res = lc.action.resource_show(id=resource_id)
    org = lc.action.organization_show(id=pkg['owner_org'])

    dataset = lc.action.recombinant_show(
        dataset_type=pkg['type'], owner_org=org['name'])

    def delete_error(err):
        return render('recombinant/resource_edit.html',
            extra_vars={
                'delete_errors': [err],
                'dataset': dataset,
                'dataset_type': dataset['dataset_type'],
                'resource': res,
                'organization': org,
                'filters': filters,
                'action': 'edit'})

    form_text = request.form.get('bulk-delete', '')
    if not form_text:
        return delete_error(_('Required field'))

    pk_fields = recombinant_primary_key_fields(res['name'])

    ok_records = []
    ok_filters = []
    records = iter(form_text.split('\n'))
    for r in records:
        r = r.rstrip('\r')
        def record_fail(err):
            # move bad record to the top of the pile
            filters['bulk-delete'] = '\n'.join(
                [r] + list(records) + ok_records)
            return delete_error(err)

        split_on = '\t' if '\t' in r else ','
        fields = [f for f in r.split(split_on)]
        if len(fields) != len(pk_fields):
            return record_fail(_('Wrong number of fields, expected {num}')
                .format(num=len(pk_fields)))

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
                u'", "'.join(fields))
        if len(found) > 1:
            return record_fail(_('Multiple matching records found'))

        if r not in ok_records:
            ok_records.append(r)
            ok_filters.append(dict(filters))

    if 'cancel' in request.form:
        return render('recombinant/resource_edit.html',
            extra_vars={
                'delete_errors': [],
                'dataset': dataset,
                'dataset_type': dataset['dataset_type'],
                'resource': res,
                'organization': org,
                'filters': {'bulk-delete': u'\n'.join(ok_records)},
                'action': 'edit'})
    if not 'confirm' in request.form:
        return render('recombinant/confirm_delete.html',
            extra_vars={
                'dataset':dataset,
                'resource':res,
                'num': len(ok_records),
                'bulk_delete': u'\n'.join(ok_records
                    # extra blank is needed to prevent field
                    # from being completely empty
                    + ([''] if '' in ok_records else [])) })

    for f in ok_filters:
        lc.action.datastore_delete(
            resource_id=resource_id,
            filters=f,
            )

    h.flash_success(_("{num} deleted.").format(num=len(ok_filters)))

    return h.redirect_to(
        'recombinant.preview_table',
        resource_name=res['name'],
        owner_org=org['name'],
        )


def _xlsx_response_headers():
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
        "EdgA/" in user_agent
        ):
            # force the XLSX file to be downloaded in MS Edge,
            # and not open in Office Apps Online.
            content_type = 'application/octet-stream'
            disposition_type = 'attachment'
    return content_type, disposition_type


@recombinant.route('/recombinant-template/<dataset_type>_<lang>_<owner_org>.xlsx', methods=['GET', 'POST'])
def template(dataset_type, lang, owner_org):

    """
    POST requests to this endpoint contain primary keys of records that are to be included in the excel file
    Parameters:
        bulk-template -> an array of strings, each string contains primary keys separated by commas
        resource_name -> the name of the resource containing the records
    """

    if lang != h.lang():
        abort(404, _('Not found'))

    lc = ckanapi.LocalCKAN(username=g.user)
    try:
        dataset = lc.action.recombinant_show(
            dataset_type=dataset_type,
            owner_org=owner_org)
        org = lc.action.organization_show(
            id=owner_org,
            include_datasets=False)
    except ckanapi.NotFound:
        abort(404, _('Not found'))

    book = excel_template(dataset_type, org)

    if request.method == 'POST':
        filters = {}
        resource_name = request.form.get('resource_name','' )
        for r in dataset['resources']:
            if r['name'] == resource_name:
                resource = r
                break
        else:
            abort(404, _("Resource not found"))

        pk_fields = recombinant_primary_key_fields(resource['name'])
        primary_keys = request.form.getlist('bulk-template')
        chromo = get_chromo(resource['name'])
        record_data = []

        for keys in primary_keys:
            temp = keys.split(",")
            for f, pkf in zip(temp, pk_fields):
                filters[pkf['datastore_id']] = f
            try:
                result = lc.action.datastore_search(resource_id=resource['id'],filters = filters)
            except NotAuthorized:
                abort(403, _(u'Unauthorized to read resource %s') % resource['id'])
            record_data += result['records']

        append_data(book, record_data, chromo)

    blob = StringIO()
    book.save(blob)
    response = Response(blob.getvalue())
    content_type, disposition_type = _xlsx_response_headers()
    response.headers['Content-Type'] = content_type
    response.headers['Content-Disposition'] = (
        '{}; filename="{}_{}_{}.xlsx"'.format(
            disposition_type,
            dataset['owner_org'],
            lang,
            dataset['dataset_type']))
    return response


@recombinant.route('/recombinant-dictionary/<dataset_type>')
def data_dictionary(dataset_type):
    try:
        geno = get_geno(dataset_type)
    except RecombinantException:
        abort(404, _('Recombinant dataset_type not found'))

    book = excel_data_dictionary(geno)
    blob = StringIO()
    book.save(blob)
    response = Response(blob.getvalue())
    content_type, disposition_type = _xlsx_response_headers()
    response.headers['Content-Type'] = content_type
    response.headers['Content-Disposition'] = '{}; filename="{}.xlsx"'.format(
        disposition_type,
        dataset_type)
    return response


@recombinant.route('/recombinant-schema/<dataset_type>.json')
def schema_json(dataset_type):
    try:
        geno = get_geno(dataset_type)
    except RecombinantException:
        abort(404, _('Recombinant dataset_type not found'))

    schema = OrderedDict()
    schema['dataset_type'] = geno['dataset_type']
    schema['title'] = OrderedDict()
    schema['notes'] = OrderedDict()

    from ckan.lib.i18n import handle_request, get_lang
    for lang in config['ckan.locales_offered'].split():
        request.environ['CKAN_LANG'] = lang
        handle_request(request, g)
        schema['title'][lang] = _(geno['title'])
        schema['notes'][lang] = _(geno['notes'])

    if 'front_matter' in geno:
        schema['front_matter'] = OrderedDict()
        for lang in sorted(geno['front_matter']):
            schema['front_matter'][lang] = geno['front_matter'][lang]

    schema['resources'] = []
    for chromo in geno['resources']:
        resource = OrderedDict()
        schema['resources'].append(resource)
        choice_fields = dict(
            (f['datastore_id'], f['choices'])
            for f in recombinant_choice_fields(
                chromo['resource_name'],
                all_languages=True))

        resource['resource_name'] = chromo['resource_name']
        resource['title'] = OrderedDict()
        for lang in config['ckan.locales_offered'].split():
            request.environ['CKAN_LANG'] = lang
            handle_request(request, g)
            resource['title'][lang] = _(chromo['title'])

        resource['primary_key'] = aslist(chromo['datastore_primary_key'])

        resource['fields'] = []
        for field in chromo['fields']:
            if not field.get('visible_to_public', True):
                continue
            fld = OrderedDict()
            resource['fields'].append(fld)
            fld['id'] = field['datastore_id']
            for k in ['label', 'description', 'validation']:
                if k in field:
                    if isinstance(field[k], dict):
                        fld[k] = field[k]
                        continue
                    fld[k] = OrderedDict()
                    for lang in config['ckan.locales_offered'].split():
                        request.environ['CKAN_LANG'] = lang
                        handle_request(request, g)
                        fld[k][lang] = _(field[k])
            if fld['id'] in resource['primary_key']:
                fld['obligation'] = 'mandatory'
            elif field.get('excel_required'):
                fld['obligation'] = 'mandatory'
            elif field.get('excel_required_formula'):
                fld['obligation'] = 'conditional'
            else:
                fld['obligation'] = 'optional'

            fld['datastore_type'] = field['datastore_type']

            if fld['id'] in choice_fields:
                choices = OrderedDict()
                fld['choices'] = choices
                for ck, cv in choice_fields[fld['id']]:
                    choices[ck] = cv

        if 'examples' in chromo:
            ex_record = chromo['examples']['record']
            example = OrderedDict()
            for field in chromo['fields']:
                if field['datastore_id'] in ex_record:
                    example[field['datastore_id']] = ex_record[
                        field['datastore_id']]
            resource['example_record'] = example

    response = Response(json.dumps(schema, indent=2, ensure_ascii=False).encode('utf-8'))
    response.headers['Content-Type'] = 'application/json'
    response.headers['Content-Disposition'] = (
        'inline; filename="{0}.json"'.format(
            dataset_type))
    return response


@recombinant.route('/recombinant/<resource_name>')
def type_redirect(resource_name):
    orgs = h.organizations_available('read')

    if not orgs:
        abort(404, _('No organizations found'))
    try:
        chromo = get_chromo(resource_name)
    except RecombinantException:
        abort(404, _('Recombinant resource_name not found'))

    return h.redirect_to(
        'recombinant.preview_table',
        resource_name=resource_name,
        owner_org=orgs[0]['name'],
    )


def dataset_redirect(package_type, id):
    lc = ckanapi.LocalCKAN(username=g.user)
    dataset = lc.action.package_show(id=id)
    return h.redirect_to(
        'recombinant.preview_table',
        resource_name=package_type,
        owner_org=dataset['organization']['name'],
    )


def resource_redirect(package_type, id, resource_id):
    return dataset_redirect(package_type, id)


@recombinant.route('/recombinant/<resource_name>/<owner_org>', methods=['GET', 'POST'])
def preview_table(resource_name, owner_org, errors=None):
    if not g.user:
        return h.redirect_to('user.login')

    org_object = Group.get(owner_org)
    if org_object.name != owner_org:
        return h.redirect_to(
            'recombinant.preview_table',
            resource_name=resource_name,
            owner_org=org_object.name,
        )

    lc = ckanapi.LocalCKAN(username=g.user, context={'ignore_auth':True})
    try:
        chromo = get_chromo(resource_name)
    except RecombinantException:
        abort(404, _('Recombinant resource_name not found'))

    if 'create' in request.form:
        # check if the user can update datasets for organization
        # admin and editors should be able to init recombinant records
        if not has_user_permission_for_group_or_org(org_object.id, g.user, 'update_dataset'):
            abort(403, _('User %s not authorized to create packages') % (str(g.user)))
        try:
            dataset = lc.action.recombinant_show(
                dataset_type=chromo['dataset_type'], owner_org=owner_org)
        except ckanapi.NotFound:
            try:
                lc.action.recombinant_create(
                    dataset_type=chromo['dataset_type'], owner_org=owner_org)
            except NotAuthorized as e:
                abort(403, e.message)
        return h.redirect_to(
            'recombinant.preview_table',
            resource_name=resource_name,
            owner_org=owner_org,
            )

    try:
        dataset = lc.action.recombinant_show(
            dataset_type=chromo['dataset_type'], owner_org=owner_org)
    except ckanapi.NotFound:
        dataset = None
    org = lc.action.organization_show(id=owner_org)

    if dataset:
        for r in dataset['resources']:
            if r['name'] == resource_name:
                break
        else:
            abort(404, _('Resource not found'))
    else:
        r = None

    return render('recombinant/resource_edit.html', extra_vars={
        'dataset': dataset,
        'dataset_type': chromo['dataset_type'],
        'resource_description': chromo['title'],
        'resource_name': chromo['resource_name'],
        'resource': r,
        'organization': org,
        'errors': errors,
        })


def _process_upload_file(lc, dataset, upload_file, geno, dry_run):
    """
    Use lc.action.datastore_upsert to load data from upload_file

    raises BadExcelData on errors.
    """
    owner_org = dataset['organization']['name']

    expected_sheet_names = dict(
        (resource['name'], resource['id'])
        for resource in dataset['resources'])

    upload_data = read_excel(upload_file)
    total_records = 0
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

        if not h.check_access('datastore_upsert', {'resource_id': expected_sheet_names[sheet_name]}):
            abort(403, _('User {0} not authorized to update resource {1}'
                        .format(str(g.user), expected_sheet_names[sheet_name])))

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
            if f.get('import_template_include', True)]
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
            [f for f in chromo['fields'] if f.get('import_template_include', True)],
            pk,
            choice_fields)
        method = 'upsert' if pk else 'insert'
        total_records += len(records)
        if not records:
            continue
        try:
            lc.action.datastore_upsert(
                method=method,
                resource_id=expected_sheet_names[sheet_name],
                records=[r[1] for r in records],
                dry_run=dry_run,
                )
        except ValidationError as e:
            if 'info' in e.error_dict:
                # because, where else would you put the error text?
                # XXX improve this in datastore, please
                pgerror = e.error_dict['info']['orig'][0].decode('utf-8')
            else:
                pgerror = e.error_dict['records'][0]
            if isinstance(pgerror, dict):
                pgerror = u'; '.join(
                    k + u': ' + u', '.join(v)
                    for k, v in pgerror.items())
            else:
                # remove some postgres-isms that won't help the user
                # when we render this as an error in the form
                pgerror = re.sub(ur'\nLINE \d+:', u'', pgerror)
                pgerror = re.sub(ur'\n *\^\n$', u'', pgerror)
            if 'records_row' in e.error_dict:
                raise BadExcelData(_(u'Sheet {0} Row {1}:').format(
                    sheet_name, records[e.error_dict['records_row']][0])
                    + u' ' + pgerror)
            raise BadExcelData(
                _(u"Error while importing data: {0}").format(
                    pgerror))
    if not total_records:
        raise BadExcelData(_("The template uploaded is empty"))
