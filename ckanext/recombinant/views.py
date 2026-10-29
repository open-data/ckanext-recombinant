from sys import maxsize as MAX_INT
from flask import Blueprint, Response as FlaskResponse
from flask_babel import force_locale
import re
import codecs
import decimal
import traceback
from uuid import UUID
import simplejson as json

from typing import Union, Dict, Tuple, Any, List, Optional, cast
from ckan.types import Response, Context

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
    get_action,
    render
)

from ckan.config.middleware.flask_app import csrf
from ckan import model
from ckan.logic import ValidationError, NotAuthorized, parse_params
from ckan.model.resource import Resource
from ckan.authz import has_user_permission_for_group_or_org, is_sysadmin

from ckan.views import nocache_store
from ckan.views.api import _finish, _finish_ok

from ckanext.recombinant.errors import (
    RecombinantException,
    RecombinantFieldError,
    BadExcelData,
    format_trigger_error
)
from ckanext.recombinant.datatypes import canonicalize
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

from ckanext.datastore.backend import DatastoreBackend
from ckanext.datastore.backend.postgres import (
    DatastorePostgresqlBackend,
    _parse_constraint_error_from_psql_error
)

from ckanapi import NotFound, LocalCKAN

# TODO: DEPRECATED: REMOVE AFTER FULL PD DATATABLES QA
import datetime
from pytz import timezone, utc
this_tz = timezone('America/Montreal')


KEY_ERROR_MATCH = re.compile('"([^"]*)"')

log = getLogger(__name__)
recombinant = Blueprint('recombinant', __name__)


def _get_recombinant_view_context_vars(
        lc: LocalCKAN,
        resource_name: str,
        owner_org: str) -> Tuple[Optional[Dict[str, Any]],
                                 Optional[Dict[str, Any]],
                                 Optional[Dict[str, Any]],
                                 List[str],
                                 Dict[str, Any],
                                 Optional[Dict[str, Any]],
                                 Optional[Dict[str, Any]],
                                 Optional[Dict[str, Any]]]:
    """
    Gets all of the common/required schemas and metadata
    for Recombinant views.

    NOTE: returns None for elements which may raise NotFound
          or RecombinantException exceptions as users would need
          to initialize the dataset and resources.

    NOTE: each view method is still responsible for raising NotFound
          exceptions / returning abort(404) for None type variables
          returned from this function.
    """
    # get the chromo
    chromo: Optional[Dict[str, Any]] = None
    try:
        chromo = get_chromo(resource_name)
    except RecombinantException:
        # Recombinant resource %s not found
        pass
    if not chromo:
        # can't do anything without a defined schema in Recombinant,
        # just do an early return of all None for speed.
        return None, None, None, [], {}, None, None, None

    # get the recombinant dict
    rcomb: Optional[Dict[str, Any]] = None
    try:
        rcomb = lc.action.recombinant_show(
            owner_org=owner_org,
            dataset_type=chromo['dataset_type'])
    except (RecombinantException, NotFound):
        # Recombinant resource %s not found
        # Recombinant dataset %s not found
        pass

    # get the resource dict
    resource: Optional[Dict[str, Any]] = None
    if rcomb:
        for r in rcomb['resources']:
            if r['name'] == resource_name:
                resource = r
                break

    # get the organization dict
    organization: Optional[Dict[str, Any]] = None
    try:
        organization = lc.action.organization_show(id=owner_org)
        if organization and organization['state'] != 'active':
            organization = None
    except NotFound:
        # Organization not found
        pass

    # get the dataset dict
    dataset: Optional[Dict[str, Any]] = None
    if rcomb:
        try:
            dataset = lc.action.package_show(id=rcomb['id'])
        except NotFound:
            # Dataset not found
            pass

    # get the geno
    geno: Optional[Dict[str, Any]] = None
    if rcomb:
        try:
            geno = get_geno(rcomb['dataset_type'])
        except RecombinantException:
            # Recombinant type %s not found
            pass

    # get the primary key field IDs as a list
    pk_fields: List[str] = []
    if chromo:
        pk_fields = aslist(chromo['datastore_primary_key'])

    # get the choice fields
    choice_fields: Dict[str, Any] = {}
    if chromo:
        choice_fields = _get_choice_fields(resource_name, org_name=owner_org)

    # return everything
    return rcomb, geno, chromo, pk_fields, choice_fields, \
        dataset, resource, organization


@recombinant.route('/resource/<id>', methods=['GET'])
def resource_alias(id: str) -> Union[Response, str]:
    """
    Redirect alias for direct resource_show view.
    """
    chromo = None
    try:
        UUID(id)  # is a normal resource id
        return abort(404)
    except ValueError:
        pass
    try:
        chromo = get_chromo(id)
    except RecombinantException:
        pass
    if not chromo or not chromo.get('published_resource_id'):
        return abort(404)
    res = Resource.get(chromo['published_resource_id'])
    if not res:
        return abort(404)
    return h.redirect_to('%s_resource.read' % res.package.type,
                         id=res.package_id,
                         package_type=res.package.type,
                         resource_id=res.id)


@recombinant.route(
    '/recombinant/upload/<resource_name>/<owner_org>',
    methods=['GET', 'POST'])
def upload(resource_name: str, owner_org: str) -> Union[Response, str]:
    if not g.user:
        return h.redirect_to('user.login')

    lc = LocalCKAN(username=g.user)
    rcomb, geno, chromo, _pk_fields, _choice_fields, \
        dataset, resource, organization = \
        _get_recombinant_view_context_vars(lc, resource_name, owner_org)

    if not geno or not chromo:
        return abort(404, _('Recombinant type %s not found') % resource_name)

    if not rcomb or not dataset or not resource:
        return abort(404, _('Resource not found'))

    if not organization:
        return abort(404, _('Organization not found'))

    if chromo.get('webform_only'):
        return abort(404, _('Excel Templating is not supported for %s') %
                     geno['dataset_type'])

    if request.method != 'POST':
        # handle page refreshes
        h.flash_notice(_('Form not submitted, please try again.'))
        return h.redirect_to('recombinant.preview_table',
                             resource_name=resource_name,
                             owner_org=owner_org)
    dry_run = 'validate' in request.form

    try:
        if not request.files['xls_update']:
            raise BadExcelData('You must provide a valid file')

        _process_upload_file(lc, dataset, request.files['xls_update'], geno, dry_run)

        if dry_run:
            h.flash_success(_("No errors found."))
        else:
            h.flash_success(_("Your file was successfully "
                              "uploaded into the central system."))

        return h.redirect_to('recombinant.preview_table',
                             resource_name=resource_name,
                             owner_org=owner_org)
    except RecombinantFieldError as e:
        h.flash_error(render('recombinant/snippets/outdated_error.html',
                             extra_vars={'key_errors': str(e).replace("'", ''),
                                         'dataset_id': dataset['id'],
                                         'res_name': resource_name,
                                         'owner_org': owner_org}))
        return h.redirect_to('recombinant.preview_table',
                             resource_name=resource_name,
                             owner_org=owner_org)
    except BadExcelData as e:
        h.flash_error(_(e.message))
        return h.redirect_to('recombinant.preview_table',
                             resource_name=resource_name,
                             owner_org=owner_org)


@recombinant.route(
    '/recombinant/manage/<resource_name>/<owner_org>/bulk-delete',
    methods=['GET', 'POST'])
def delete_records(resource_name: str, owner_org: str) -> Union[str, Response]:
    """
    Bulk delete records via Delete tab UI.
    Separated by newlines in a textare form field.
    """
    if not g.user:
        return h.redirect_to('user.login')

    lc = LocalCKAN(username=g.user)
    rcomb, geno, chromo, pk_fields, _choice_fields, \
        dataset, resource, organization = \
        _get_recombinant_view_context_vars(lc, resource_name, owner_org)

    if not geno or not chromo:
        return abort(404, _('Recombinant type %s not found') % resource_name)

    if not rcomb or not dataset or not resource:
        return abort(404, _('Resource not found'))

    if not organization:
        return abort(404, _('Organization not found'))

    if not h.check_access('datastore_records_delete',
                          {'resource_id': resource['id'], 'filters': {}}):
        return abort(403, _('User {0} not authorized '
                            'to update resource {1}').format(str(g.user),
                                                             resource['id']))

    if request.method != 'POST':
        # handle page refreshes
        h.flash_notice(_('Form not submitted, please try again.'))
        return h.redirect_to('recombinant.preview_table',
                             resource_name=resource_name,
                             owner_org=owner_org)

    # type_ignore_reason: [] default is allowed
    def delete_error(err: str, _records: List[str] = []) -> str:  # type: ignore
        return render('recombinant/confirm_delete.html',
                      extra_vars={'recomb': rcomb,
                                  'resource': resource,
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
        return h.redirect_to('recombinant.preview_table',
                             resource_name=resource_name,
                             owner_org=owner_org)

    filters = {}
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
            filters[pkf] = f
        try:
            result = lc.action.datastore_search(
                resource_id=resource['id'],
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
        return h.redirect_to('recombinant.preview_table',
                             resource_name=resource_name,
                             owner_org=owner_org)
    # type_ignore_reason: incomplete typing
    if 'confirm' not in request.form or request.method == 'GET':  # type: ignore
        return render('recombinant/confirm_delete.html',
                      extra_vars={'rcomb': dataset,
                                  'resource': resource,
                                  'num': len(ok_records),
                                  'bulk_delete': '\n'.join(
                                      ok_records
                                      # extra blank is needed to prevent field
                                      # from being completely empty
                                      + ([''] if '' in ok_records else []))})
    if request.method == 'POST':
        for f in ok_filters:
            try:
                lc.action.datastore_delete(resource_id=resource['id'],
                                           filters=f)
            except ValidationError as e:
                if 'constraint_info' in e.error_dict:
                    error_message = _render_recombinant_constraint_errors(
                        lc, e, chromo, 'delete')
                    h.flash_error(error_message)
                    # type_ignore_reason: incomplete typing
                    return record_fail(error_message)  # type: ignore
                raise

        h.flash_success(_("{num} deleted.").format(num=len(ok_filters)))

    return h.redirect_to('recombinant.preview_table',
                         resource_name=resource_name,
                         owner_org=owner_org)


@recombinant.route(
    '/recombinant/manage/<resource_name>/<owner_org>/delete-single-record/<pk>',
    methods=['GET', 'POST'])
def delete_single_record(resource_name: str, owner_org: str,
                         pk: str) -> Union[str, Response]:
    """
    Delete a single record for a Recombinant resource.
    """
    if not g.user:
        return h.redirect_to('user.login')

    lc = LocalCKAN(username=g.user)
    rcomb, geno, chromo, pk_fields, _choice_fields, \
        dataset, resource, organization = \
        _get_recombinant_view_context_vars(lc, resource_name, owner_org)

    if not geno or not chromo:
        return abort(404, _('Recombinant type %s not found') % resource_name)

    if not rcomb or not dataset or not resource:
        return abort(404, _('Resource not found'))

    if not organization:
        return abort(404, _('Organization not found'))

    if not h.check_access('datastore_records_delete',
                          {'resource_id': resource['id'], 'filters': {}}):
        return abort(403, _('User {0} not authorized '
                            'to update resource {1}').format(str(g.user),
                                                             resource['id']))

    primary_key_vals = [_url_part_unescape(p) for p in pk.split(',')]
    came_from = request.form.get('came_from') if request.method == 'POST' \
        else request.args.get('came_from')
    if came_from not in ['preview_record', 'preview_table']:
        came_from = 'preview_table'  # default to preview_table view

    if 'cancel' in request.form:
        if came_from == 'preview_record':
            return h.redirect_to('recombinant.preview_record',
                                 resource_name=resource_name,
                                 owner_org=owner_org,
                                 pk=pk)
        return h.redirect_to('recombinant.preview_table',
                             resource_name=resource_name,
                             owner_org=owner_org)
    if request.method != 'POST' or 'confirm' not in request.form:
        return render('recombinant/confirm_single_delete.html',
                      extra_vars={
                          'rcomb': rcomb,
                          'resource': resource,
                          'num': 1,
                          'pk': pk,
                          'pk_list': primary_key_vals,
                          'came_from': came_from})

    filters = {}
    try:
        for i, k in enumerate(pk_fields):
            filters[k] = primary_key_vals[i]
    except IndexError:
        abort(404, _('Record %s not found for Organization %s') %
              (pk, owner_org))

    try:
        lc.action.datastore_records_delete(
            resource_id=resource['id'], filters=filters)
    except NotFound:
        h.flash_error(_('Not found') + ' ' + str(filters))
    except ValidationError as e:
        if 'constraint_info' in e.error_dict:
            error_message = _render_recombinant_constraint_errors(
                lc, e, chromo, 'delete')
            h.flash_error(error_message)
            if came_from == 'preview_record':
                return h.redirect_to('recombinant.preview_record',
                                     resource_name=resource_name,
                                     owner_org=owner_org,
                                     pk=pk)
            return h.redirect_to('recombinant.preview_table',
                                 resource_name=resource_name,
                                 owner_org=owner_org)
        raise

    h.flash_success(_("Deleted record {key}.").format(
        key=','.join(primary_key_vals)))

    return h.redirect_to('recombinant.preview_table',
                         resource_name=resource_name,
                         owner_org=owner_org)


@recombinant.route(
    '/recombinant/manage/<resource_name>/<owner_org>/delete-selected-records',
    methods=['GET', 'POST'])
def delete_selected_records(resource_name: str,
                            owner_org: str) -> Union[str, Response]:
    """
    Delete selected records for a Recombinant resource,
    selectable from the DataTables UI.
    """
    if not g.user:
        return h.redirect_to('user.login')

    lc = LocalCKAN(username=g.user)
    rcomb, geno, chromo, pk_fields, _choice_fields, \
        dataset, resource, organization = \
        _get_recombinant_view_context_vars(lc, resource_name, owner_org)

    if not geno or not chromo:
        return abort(404, _('Recombinant type %s not found') % resource_name)

    if not rcomb or not dataset or not resource:
        return abort(404, _('Resource not found'))

    if not organization:
        return abort(404, _('Organization not found'))

    if not h.check_access('datastore_records_delete',
                          {'resource_id': resource['id'], 'filters': {}}):
        return abort(403, _('User {0} not authorized '
                            'to update resource {1}').format(str(g.user),
                                                             resource['id']))

    records = request.form.getlist('select-delete')

    if 'cancel' in request.form:
        return h.redirect_to('recombinant.preview_table',
                             resource_name=resource_name,
                             owner_org=owner_org)
    if request.method != 'POST' or 'confirm' not in request.form:
        return render('recombinant/confirm_select_delete.html',
                      extra_vars={
                          'rcomb': rcomb,
                          'resource': resource,
                          'num': len(records),
                          'select_delete': ';'.join(records)})

    records = ''.join(records).split(';')

    records_deleted = 0
    for r in records:
        filter = dict(zip(pk_fields, r.split(',')))
        if filter:
            try:
                lc.action.datastore_records_delete(
                    resource_id=resource['id'],
                    filters=filter)
                records_deleted += 1
            except NotFound:
                h.flash_error(_('Not found') + ' ' + str(filter))
            except ValidationError as e:
                if 'constraint_info' in e.error_dict:
                    error_message = _render_recombinant_constraint_errors(
                        lc, e, chromo, 'delete')
                    h.flash_error(error_message)
                    return h.redirect_to('recombinant.preview_table',
                                         resource_name=resource_name,
                                         owner_org=owner_org)
                raise

    h.flash_success(_("{num} deleted.").format(num=records_deleted))

    return h.redirect_to('recombinant.preview_table',
                         resource_name=resource_name,
                         owner_org=owner_org)


@recombinant.route(
    '/recombinant/manage/<resource_name>/<owner_org>/delete_dataset',
    methods=['GET', 'POST'])
def delete_dataset(resource_name: str, owner_org: str) -> Union[str, Response]:
    """
    UI for sysadmins to delete an entire Recombinant dataset. This will
    delete the datastore table, the resources, and the dataset.

    Cannot delete the dataset if any of the resources have datastore data.
    """
    if not is_sysadmin(g.user):
        # only sysadmins can delete via UI
        return abort(403)

    lc = LocalCKAN(username=g.user)
    rcomb, geno, chromo, _pk_fields, _choice_fields, \
        dataset, resource, organization = \
        _get_recombinant_view_context_vars(lc, resource_name, owner_org)

    if not geno or not chromo:
        return abort(404, _('Recombinant type %s not found') % resource_name)

    if not rcomb or not dataset or not resource:
        return abort(404, _('Dataset not found'))

    if not organization:
        return abort(404, _('Organization not found'))

    if request.method != 'POST':
        # handle page refreshes
        h.flash_notice(_('Form not submitted, please try again.'))
        return h.redirect_to('recombinant.preview_table',
                             resource_name=resource_name,
                             owner_org=owner_org)

    for r in rcomb.get('resources', []):
        _l = r['shortname']
        try:
            result = lc.action.datastore_search(resource_id=r['id'], limit=0)
        except NotFound:
            continue
        if result.get('total', 0) > 0:
            h.flash_error(_('Cannot delete dataset because \"%s\" contains records.') %
                          _(_l))
            return h.redirect_to('recombinant.preview_table',
                                 resource_name=resource_name,
                                 owner_org=owner_org)

    if 'cancel' in request.form:
        return h.redirect_to('recombinant.preview_table',
                             resource_name=resource_name,
                             owner_org=owner_org)
    # type_ignore_reason: incomplete typing
    if 'confirm' not in request.form or request.method == 'GET':  # type: ignore
        return render('recombinant/confirm_dataset_delete.html',
                      extra_vars={'rcomb': rcomb,
                                  'resource': resource,
                                  'organization': organization})
    if request.method == 'POST':
        # delete datastore tables
        for r in rcomb.get('resources', []):
            _l = r['shortname']
            try:
                lc.action.datastore_delete(resource_id=r['id'])
                h.flash_success(_('Deleted table for \"%s\"') % _(_l))
            except NotFound:
                pass
            try:
                lc.action.resource_delete(id=r['id'])
                h.flash_success(_('Deleted resource for \"%s\"') % _(_l))
            except NotFound:
                pass
        try:
            lc.action.package_delete(id=dataset['id'])
            h.flash_success(_('Deleted dataset'))
        except NotFound:
            pass

    return h.redirect_to('recombinant.preview_table',
                         resource_name=resource_name,
                         owner_org=owner_org)


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


@recombinant.route('/recombinant/template/<dataset_type>_<lang>_<owner_org>.xlsx',
                   methods=['GET', 'POST'])
@nocache_store
def template(dataset_type: str, lang: str, owner_org: str) -> Union[Response, str]:
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

    for r in dataset.get('resources'):
        chromo = get_chromo(r['name'])
        if chromo.get('webform_only'):
            return abort(404, _('Excel Templating is not supported for %s') %
                         dataset_type)

    if request.method == 'GET':
        try:
            book = excel_template(dataset_type, org)
        except RecombinantException as e:
            return abort(400, _('Unable to download template.\n%s') % e)

    else:
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

        edit_using__id = bool(chromo.get('edit_using__id'))
        if edit_using__id:
            pk_fields = [{'datastore_id': '_id'}]

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

        try:
            book = excel_template(
                dataset_type, org, edit_using__id, len(record_data))
        except RecombinantException as e:
            return abort(400, _('Unable to download template.\n%s') % e)

        try:
            append_data(book, record_data, chromo, edit_using__id)
        except RecombinantFieldError as e:
            h.flash_error(render('recombinant/snippets/outdated_error.html',
                                 extra_vars={'key_errors': str(e).replace("'", ''),
                                             'dataset_id': dataset['id'],
                                             'res_name': resource_name,
                                             'owner_org': dataset['owner_org']}))
            return h.redirect_to('recombinant.preview_table',
                                 resource_name=resource_name,
                                 owner_org=org['name'])

        # Get Referential Records:
        # we should not assume that the Foreign Keys will be the same
        # as the Primary Keys. Thus, we need to check the values in
        # record_data and datastore_search with filters in the scenario
        # that there are multiple Foreign Keys for one table. This
        # should give the exact referenced/referencing records.
        ds_info = lc.action.datastore_info(id=resource['id'])
        if 'foreignkeys' in ds_info['meta']:
            resource_names = dict((r['id'], r['name']) for r in dataset['resources'])
            for fk in ds_info['meta']['foreignkeys']:
                f_chromo = None
                ref_record_data = []
                if resource['id'] == fk['child_table']:
                    if fk['parent_table'] not in resource_names:
                        # do not include records from resources not in this dataset
                        continue
                    f_chromo = get_chromo(resource_names[fk['parent_table']])
                    f_completed_filters = []
                    for selected_record in record_data:
                        # use the datastore_info column mapping as the
                        # column names may be different between tables
                        f_filters = dict(
                            (fk_pc, selected_record[fk['child_columns'][fk_pi]])
                            for fk_pi, fk_pc in enumerate(fk['parent_columns']))
                        if f_filters in f_completed_filters:
                            # prevent duplicate data retrieval
                            continue
                        f_completed_filters.append(f_filters)
                        result = lc.action.datastore_search(
                            resource_id=fk['parent_table'], filters=f_filters)
                        ref_record_data += result['records']
                elif resource['id'] == fk['parent_table']:
                    if fk['child_table'] not in resource_names:
                        # do not include records from resources not in this dataset
                        continue
                    f_chromo = get_chromo(resource_names[fk['child_table']])
                    f_completed_filters = []
                    for selected_record in record_data:
                        # use the datastore_info column mapping as the
                        # column names may be different between tables
                        f_filters = dict(
                            (fk_cc, selected_record[fk['parent_columns'][fk_ci]])
                            for fk_ci, fk_cc in enumerate(fk['child_columns']))
                        if f_filters in f_completed_filters:
                            # prevent duplicate data retrieval
                            continue
                        f_completed_filters.append(f_filters)
                        result = lc.action.datastore_search(
                            resource_id=fk['child_table'], filters=f_filters)
                        ref_record_data += result['records']
                if ref_record_data and f_chromo is not None:
                    append_data(book, ref_record_data, f_chromo)

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
                     published_resource: bool = False,
                     org_name: Optional[str] = None) -> Response:
    try:
        geno = get_geno(dataset_type)
        org = get_action('organization_show')(
            {}, {'id': org_name}) if org_name else None
    except RecombinantException:
        return abort(404, _('Recombinant dataset_type not found'))
    except (NotAuthorized, NotFound):
        return abort(404, _('Organization not found'))

    book = excel_data_dictionary(geno, published_resource=published_resource,
                                 org=org)
    filename = f'{org_name}_{dataset_type}.xlsx' \
        if org_name else f'{dataset_type}.xlsx'
    blob = BytesIO()
    book.save(blob)
    response = FlaskResponse(blob.getvalue())
    content_type, disposition_type = _xlsx_response_headers()
    response.headers['Content-Type'] = content_type
    response.headers['Content-Disposition'] = '{}; filename="{}"'.format(
        disposition_type,
        filename)
    return response


@recombinant.route('/recombinant/dictionary/<org_name>_<dataset_type>')
@nocache_store
def org_based_data_dictionary(org_name: str, dataset_type: str) -> Response:
    return _data_dictionary(dataset_type, published_resource=False, org_name=org_name)


@recombinant.route('/recombinant/dictionary/<dataset_type>')
@nocache_store
def data_dictionary(dataset_type: str) -> Response:
    return _data_dictionary(dataset_type, published_resource=False)


@recombinant.route('/recombinant/published-dictionary/<dataset_type>')
@nocache_store
def published_data_dictionary(dataset_type: str) -> Response:
    return _data_dictionary(dataset_type, published_resource=True)


def _schema_json(dataset_type: str, published_resource: bool = False,
                 org_name: Optional[str] = None) -> Response:
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
            all_languages=True,
            org_name=org_name)

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

            if field.get('choices_suffix_filter'):
                fld['choices_suffixes'] = field['choices_suffix_filter']

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


@recombinant.route('/recombinant/schema/<org_name>_<dataset_type>.json')
@nocache_store
def org_based_schema_json(org_name: str, dataset_type: str) -> Response:
    return _schema_json(dataset_type, published_resource=False, org_name=org_name)


@recombinant.route('/recombinant/schema/<dataset_type>.json')
@nocache_store
def schema_json(dataset_type: str) -> Response:
    return _schema_json(dataset_type, published_resource=False)


@recombinant.route('/recombinant/published-schema/<dataset_type>.json')
@nocache_store
def published_schema_json(dataset_type: str) -> Response:
    return _schema_json(dataset_type, published_resource=True)


@recombinant.route('/recombinant/<resource_name>')
def type_redirect(resource_name: str, dataset_id: Optional[str] = None) -> Response:
    """
    Redirects Recombinant routes without an organization name in the URI.
    """
    orgs = h.organizations_available('read')

    if not orgs:
        return abort(404, _('No organizations found'))
    try:
        get_chromo(resource_name)
    except RecombinantException:
        return abort(404, _('Recombinant resource %s not found') % resource_name)

    # go to first org in user's available list
    owner_org_name = orgs[0]['name']
    if is_sysadmin(g.user):
        # if sysadmin, always go to configured org, default tbs-sct
        owner_org_name = config['ckanext.recombinant.sysadmin_org_redirect']

    if dataset_id:
        # support for dataset ID redirects
        try:
            dataset = get_action('package_show')(
                {'user': g.user}, {'id': dataset_id})
        except NotAuthorized:
            return abort(403)
        except NotFound:
            return abort(404)

        if dataset.get('owner_org'):
            org_obj = model.Group.get(dataset.get('owner_org'))
            if org_obj:
                owner_org_name = org_obj.name

    return h.redirect_to('recombinant.preview_table',
                         resource_name=resource_name,
                         owner_org=owner_org_name)


def dataset_redirect(package_type: str, id: str) -> Response:
    lc = LocalCKAN(username=g.user)
    dataset = lc.action.package_show(id=id)
    return h.redirect_to('recombinant.preview_table',
                         resource_name=package_type,
                         owner_org=dataset['organization']['name'])


def resource_redirect(package_type: str, id: str, resource_id: str) -> Response:
    return dataset_redirect(package_type, id)


@recombinant.route('/recombinant/<resource_name>/<owner_org>', methods=['GET', 'POST'])
def preview_table(resource_name: str,
                  owner_org: str) -> Union[str, Response]:
    """
    Main view for Recombinant resource and dataset edit/create functionalities.
    """
    if not g.user:
        return h.redirect_to('user.login')

    lc = LocalCKAN(username=g.user, context={'ignore_auth': True})
    rcomb, geno, chromo, pk_fields, choice_fields, \
        dataset, resource, organization = \
        _get_recombinant_view_context_vars(lc, resource_name, owner_org)

    if not chromo:
        return abort(404, _('Recombinant type %s not found') % resource_name)

    if not organization:
        return abort(404, _('Organization not found'))

    if organization['name'] != owner_org:
        return h.redirect_to('recombinant.preview_table',
                             resource_name=resource_name,
                             owner_org=organization['name'])

    if resource and not h.check_access('datastore_upsert',
                                       {'resource_id': resource['id']}):
        return abort(403, _('Not authoirzed to manage Recombinant resource.'))

    template_vars = {
        'rcomb': rcomb,
        'geno': geno,
        'chromo': chromo,
        'pk_fields': pk_fields,
        'choice_fields': choice_fields,
        'dataset': dataset,
        'resource': resource,
        'organization': organization,
    }

    # check that the resource has errors
    has_errors = False
    if resource and (
        'error' in resource or
        not resource['datastore_correct'] or
        not resource['schema_correct']
    ):
        has_errors = True

    if (
      'create' in request.form or
      'create-resource' in request.form or
      'refresh-hard' in request.form or
      'refresh' in request.form
    ):
        # check if the user can update datasets for organization
        # admin and editors should be able to init recombinant records
        if not has_user_permission_for_group_or_org(organization['id'],
                                                    g.user,
                                                    'update_dataset'):
            return abort(403, _('User %s not authorized to create packages') %
                         (str(g.user)))
        if not dataset or has_errors:
            try:
                if 'create' in request.form:
                    # brand new dataset
                    lc.action.recombinant_create(
                        dataset_type=chromo['dataset_type'], owner_org=owner_org)
                    h.flash_success(_('Resources successfully created.'))
                elif 'create-resource' in request.form:
                    # missing resources
                    lc.action.recombinant_update(
                        dataset_type=chromo['dataset_type'], owner_org=owner_org)
                    h.flash_success(_('Resource successfully created.'))
                elif 'refresh-hard' in request.form or 'refresh' in request.form:
                    # missing datastore table or fields
                    if not is_sysadmin(g.user):
                        # only sysadmins can refresh via UI
                        return abort(403)
                    delete_fields = False
                    if 'refresh-hard' in request.form:
                        delete_fields = True
                    lc.action.recombinant_update(
                        dataset_type=chromo['dataset_type'], owner_org=owner_org,
                        force_update=True,
                        delete_fields=delete_fields)
                    h.flash_success(_('Resources successfully refreshed.'))
            except NotAuthorized as e:
                return abort(403, e.message or '')
        return h.redirect_to('recombinant.preview_table',
                             resource_name=resource_name,
                             owner_org=owner_org)

    record_state = request.form.get('record_state') \
        if 'record_state' in request.form else request.args.get(
            'record_state', '')
    records = None
    record_query = None
    record_query_error = None
    pk_labels = []
    pk_field_dicts = recombinant_primary_key_fields(resource_name)
    for f in pk_field_dicts:
        pk_labels.append(h.recombinant_language_text(f['label']))
    if chromo.get('display_card') and resource:
        record_query = request.form.get('record_query') \
            if 'record_query' in request.form else request.args.get(
                'record_query', '')
        filters = {}
        if record_query:
            string_query = record_query.split(',')
            log.info(string_query)
            try:
                for i, k in enumerate(pk_fields):
                    filters[k] = string_query[i]
            except IndexError:
                record_query_error = _('Invalid search parameter "%s". Expected: %s') \
                    % (record_query, ','.join(pk_labels))
                pass
        if record_state and chromo['stately_records']:
            filters['record_state'] = record_state
        try:
            result = lc.action.datastore_search(resource_id=resource['id'],
                                                filters=filters,
                                                limit=MAX_INT)
            if result and 'records' in result:
                records = result['records']
        except ValidationError:
            record_query_error = _('Invalid search parameter "%s". Expected: %s') \
                % (record_query, ','.join(pk_labels))
        except NotFound:
            pass  # resource/dataset not initialized yet
        except NotAuthorized:
            return abort(403, _('Unauthorized to read resource %s') % resource['id'])

    return render('recombinant/resource_edit.html',
                  extra_vars=dict(template_vars,
                                  # NOTE: magic key, assigned during definition
                                  #       loading in main plugin class.
                                  dataset_type=chromo['dataset_type'],
                                  records=records,
                                  record_query=record_query,
                                  record_query_error=record_query_error,
                                  record_state=record_state,
                                  pk_labels=pk_labels,
                                  errors=None,
                                  delete_errors=None,
                                  filters=None))


@recombinant.route('/recombinant/<resource_name>/<owner_org>/<pk>',
                   methods=['GET'])
def preview_record(resource_name: str,
                   owner_org: str,
                   pk: str) -> Union[str, Response]:
    """
    Preview a single record.
    """
    if not g.user:
        return h.redirect_to('user.login')

    lc = LocalCKAN(username=g.user, context={'ignore_auth': True})
    rcomb, geno, chromo, pk_fields, choice_fields, \
        dataset, resource, organization = \
        _get_recombinant_view_context_vars(lc, resource_name, owner_org)

    if not geno or not chromo:
        return abort(404, _('Recombinant type %s not found') % resource_name)

    if not rcomb or not dataset or not resource:
        return abort(404, _('Resource not found'))

    if not organization:
        return abort(404, _('Organization not found'))

    if organization['name'] != owner_org:
        return h.redirect_to('recombinant.preview_record',
                             resource_name=resource_name,
                             owner_org=organization['name'],
                             pk=pk)

    if not h.check_access('datastore_search', {'resource_id': resource['id']}):
        return abort(403, _('Not authorized to view resource.'))

    template_vars = {
        'rcomb': rcomb,
        'geno': geno,
        'chromo': chromo,
        'pk_fields': pk_fields,
        'choice_fields': choice_fields,
        'dataset': dataset,
        'resource': resource,
        'organization': organization,
    }

    primary_key_vals = [_url_part_unescape(p) for p in pk.split(',')]

    record = None
    filters = {}
    try:
        for i, k in enumerate(pk_fields):
            filters[k] = primary_key_vals[i]
    except IndexError:
        abort(404, _('Record %s not found for Organization %s') %
              (pk, owner_org))

    try:
        result = lc.action.datastore_search(
            resource_id=resource['id'], filters=filters, limit=1)
        if len(result['records']) == 0:
            return abort(404, _('Record %s not found for Organization %s') %
                         (pk, owner_org))
        record = result['records'][0]
    except NotAuthorized:
        return abort(403, _('Unauthorized to read resource %s') % resource['id'])

    return render('recombinant/record_preview.html',
                  extra_vars=dict(template_vars,
                                  pk=pk,
                                  record=record))


@recombinant.route('/recombinant/manage/<resource_name>/<owner_org>/create-record',
                   methods=['GET', 'POST'])
def create_record(resource_name: str, owner_org: str) -> Union[str, Response]:
    """
    Create a single record via a webform.
    """
    if not g.user:
        return h.redirect_to('user.login')

    lc = LocalCKAN(username=g.user)
    rcomb, geno, chromo, pk_fields, choice_fields, \
        dataset, resource, organization = \
        _get_recombinant_view_context_vars(lc, resource_name, owner_org)

    if not geno or not chromo:
        return abort(404, _('Recombinant type %s not found') % resource_name)

    if not rcomb or not dataset or not resource:
        return abort(404, _('Resource not found'))

    if not organization:
        return abort(404, _('Organization not found'))

    if not chromo.get('create_form'):
        return abort(404, _('Create Record form not supported for type %s') %
                     geno['dataset_type'])

    if not h.check_access('datastore_upsert', {'resource_id': resource['id']}):
        return abort(403, _('Unauthorized to create a record for this resource'))

    template_vars = {
        'rcomb': rcomb,
        'geno': geno,
        'chromo': chromo,
        'pk_fields': pk_fields,
        'choice_fields': choice_fields,
        'dataset': dataset,
        'resource': resource,
        'organization': organization,
    }

    if request.method == 'POST':
        post_data = parse_params(request.form, ignore_keys=['save'])

        if 'cancel' in post_data:
            return h.redirect_to('recombinant.preview_table',
                                 resource_name=resource_name,
                                 owner_org=rcomb['owner_org'])

        data, err = _clean_check_type_errors(
            post_data,
            chromo['fields'],
            pk_fields,
            choice_fields)
        error_summary = None
        # normalize newlines to \n
        data = _normalize_record_newlines(data)
        try:
            lc.action.datastore_upsert(
                resource_id=resource['id'],
                method='insert',
                records=[{k: None if k in err else v for (k, v) in data.items()}],
                dry_run=bool(err))
        except ValidationError as ve:
            if 'records' in ve.error_dict:
                try:
                    # type_ignore_reason: incomplete typing
                    err = dict({
                        k: list(format_trigger_error(v))
                        for (k, v) in
                        ve.error_dict['records'][0].items()  # type: ignore
                    }, **err)
                except AttributeError:
                    # type_ignore_reason: incomplete typing
                    if (
                      'duplicate key value violates unique constraint' in
                      ve.error_dict['records'][0]):  # type: ignore
                        err = dict({
                            k: [_("This record already exists")]
                            for k in pk_fields
                        }, **err)
                    elif (
                      'constraint_info' in ve.error_dict):
                        error_summary = _render_recombinant_constraint_errors(
                            lc, ve, chromo, 'upsert')
                    else:
                        log.warning('Failed to create %s record for org %s:\n%s',
                                    resource_name, owner_org, traceback.format_exc())
                        error_summary = _('Something went wrong, your record '
                                          'was not created. Please contact support.')
            # type_ignore_reason: incomplete typing
            elif ve.error_dict.get(
                    'info', {}).get('pgcode', '') == '23505':  # type: ignore
                err = dict({
                    k: [_("This record already exists")]
                    for k in pk_fields
                }, **err)
            else:
                log.warning('Failed to create %s record for org %s:\n%s',
                            resource_name, owner_org, traceback.format_exc())
                error_summary = _('Something went wrong, your record '
                                  'was not created. Please contact support.')

        if err or error_summary:
            return render('recombinant/create_record.html',
                          extra_vars=dict(template_vars,
                                          data=data,
                                          # prevent rendering error on parent template
                                          pkg_dict={},
                                          errors=err,
                                          error_summary=error_summary))

        h.flash_notice(_('Record Created'))

        return h.redirect_to('recombinant.preview_table',
                             resource_name=resource_name,
                             owner_org=rcomb['owner_org'])

    return render('recombinant/create_record.html',
                  extra_vars=dict(template_vars,
                                  data={},
                                  # prevent rendering error on parent template
                                  pkg_dict={},
                                  errors={}))


@recombinant.route(
    '/recombinant/manage/<resource_name>/<owner_org>/update-record/<pk>',
    methods=['GET', 'POST'])
def update_record(resource_name: str, owner_org: str, pk: str) -> Union[str, Response]:
    """
    Update a single record via a webform.
    """
    if not g.user:
        return h.redirect_to('user.login')

    lc = LocalCKAN(username=g.user)
    rcomb, geno, chromo, pk_fields, choice_fields, \
        dataset, resource, organization = \
        _get_recombinant_view_context_vars(lc, resource_name, owner_org)

    if not geno or not chromo:
        return abort(404, _('Recombinant type %s not found') % resource_name)

    if not rcomb or not dataset or not resource:
        return abort(404, _('Resource not found'))

    if not organization:
        return abort(404, _('Organization not found'))

    if not chromo.get('edit_form'):
        return abort(404, _('Edit Record form not supported for type %s') %
                     geno['dataset_type'])

    if not h.check_access('datastore_upsert', {'resource_id': resource['id']}):
        return abort(403, _('Unauthorized to update a record for this resource'))

    template_vars = {
        'rcomb': rcomb,
        'geno': geno,
        'chromo': chromo,
        'pk_fields': pk_fields,
        'choice_fields': choice_fields,
        'dataset': dataset,
        'resource': resource,
        'organization': organization,
    }

    pk_list = [_url_part_unescape(p) for p in pk.split(',')]
    came_from = request.form.get('came_from') if request.method == 'POST' \
        else request.args.get('came_from')
    if came_from not in ['preview_record', 'preview_table']:
        came_from = 'preview_table'  # default to preview_table view

    pk_filter = dict(zip(pk_fields, pk_list))

    records = lc.action.datastore_search(
        resource_id=resource['id'],
        filters=pk_filter)['records']
    if len(records) == 0:
        abort(404, _('Not found'))
    if len(records) > 1:
        abort(400, _('Multiple records found'))
    record = records[0]

    data = {}
    for f in chromo['fields']:
        if (
          not f.get('import_template_include', True) or
          f.get('published_resource_computed_field', False)
        ):
            continue
        val = record[f['datastore_id']]
        if val and f.get('datastore_type') == 'money':
            if isinstance(val, str) and '$' in val:
                data[f['datastore_id']] = val
            else:
                data[f['datastore_id']] = '${:,.2f}'.format(val)
        else:
            data[f['datastore_id']] = val

    if request.method == 'POST':
        post_data = parse_params(request.form, ignore_keys=['save'] + pk_fields)

        if 'cancel' in post_data:
            if came_from == 'preview_record':
                return h.redirect_to('recombinant.preview_record',
                                     resource_name=resource_name,
                                     owner_org=rcomb['owner_org'],
                                     pk=pk)
            return h.redirect_to('recombinant.preview_table',
                                 resource_name=resource_name,
                                 owner_org=rcomb['owner_org'])

        data, err = _clean_check_type_errors(
            post_data,
            chromo['fields'],
            pk_fields,
            choice_fields)
        error_summary = None
        # can't change pk fields
        for f_id in data:
            if f_id in pk_fields:
                data[f_id] = record[f_id]

        # normalize newlines to \n
        data = _normalize_record_newlines(data)

        try:
            lc.action.datastore_upsert(
                resource_id=resource['id'],
                # method='update',    FIXME not raising ValidationErrors
                records=[{k: None if k in err else v for (k, v) in data.items()}],
                dry_run=bool(err))
        except ValidationError as ve:
            try:
                # type_ignore_reason: incomplete typing
                err = dict({
                    k: list(format_trigger_error(v))
                    for (k, v) in ve.error_dict['records'][0].items()  # type: ignore
                }, **err)
            except AttributeError:
                log.warning('Failed to update %s record for org %s:\n%s',
                            resource_name, owner_org, traceback.format_exc())
                error_summary = _('Something went wrong, your record '
                                  'was not updated. Please contact support.')

        if err or error_summary:
            return render('recombinant/update_record.html',
                          extra_vars=dict(template_vars,
                                          data=data,
                                          pk=pk,
                                          # prevent rendering error on parent template
                                          pkg_dict={},
                                          errors=err,
                                          error_summary=error_summary,
                                          came_from=came_from))

        h.flash_notice(_('Record %s Updated') % ','.join(pk_list))

        if came_from == 'preview_record':
            return h.redirect_to('recombinant.preview_record',
                                 resource_name=resource_name,
                                 owner_org=rcomb['owner_org'],
                                 pk=pk)

        return h.redirect_to('recombinant.preview_table',
                             resource_name=resource_name,
                             owner_org=rcomb['owner_org'])

    return render('recombinant/update_record.html',
                  extra_vars=dict(template_vars,
                                  data=data,
                                  pk=pk,
                                  # prevent rendering error on parent template
                                  pkg_dict={},
                                  errors={},
                                  came_from=came_from))


@recombinant.route('/recombinant/manage/<resource_name>/<owner_org>/upsert-data',
                   methods=['POST'])
def upsert_data(resource_name: str, owner_org: str) -> Union[str, Response]:
    """
    Wrapper to datastore_upsert with specific logic for custom DataTables.

    Allows for encoded POSTed form data as a JSON string in the records field.
    This allows for easy CSRF Token validation in AJAX requests.

    Adds custom message handling for DataTables.
    """
    if not h.is_registry_domain():
        return abort(404)

    context = cast(Context, {'user': g.user, 'model': model})

    data_dict = parse_params(request.form, ignore_keys=[g.csrf_field_name])
    if 'records' in data_dict:
        try:
            # type_ignore_reason: incomplete typing
            data_dict['records'] = json.loads(data_dict['records'])  # type: ignore
        except (KeyError, ValueError):
            pass

    return_dict = {}
    lc = LocalCKAN()
    chromo = get_chromo(resource_name)
    pk_fields = aslist(chromo['datastore_primary_key'])
    offset = 0
    records = data_dict.get('records', [])
    resource_id = data_dict.get('resource_id')
    dry_run = data_dict.get('dry_run')
    method = data_dict.get('method')
    # NOTE: upserting each record one-by-one is crazy slower,
    #       but it is the only way to get all of the errors back in one object.
    while offset < len(records):
        # type_ignore_reason: incomplete typing
        record = _normalize_record_newlines(records[offset])  # type: ignore
        try:
            data = get_action('datastore_upsert')(
                context, {
                    'method': method,
                    'resource_id': resource_id,
                    'dry_run': dry_run,
                    'records': [record]
                })
            if 'result' not in return_dict:
                return_dict['result'] = {}
            return_dict['result']['row_{}'.format(offset)] = data
            return_dict['success'] = True
            offset += 1
        except NotAuthorized:
            return_dict['error'] = {'__type': 'Authorization Error',
                                    'message': _('Access denied')}
            return_dict['success'] = False
            return _finish(403, return_dict, content_type='json')
        except NotFound:
            return_dict['error'] = {'__type': 'Not Found Error',
                                    'message': _('Not found')}
            return_dict['success'] = False
            return _finish(404, return_dict, content_type='json')
        except ValidationError as ve:
            err = {}
            error_summary = None
            if 'records' in ve.error_dict:
                try:
                    # type_ignore_reason: incomplete typing
                    err = dict({
                        k: list(format_trigger_error(v))
                        for (k, v) in
                        ve.error_dict['records'][0].items()  # type: ignore
                    }, **err)
                except AttributeError:
                    # type_ignore_reason: incomplete typing
                    if (
                      'duplicate key value violates unique constraint' in
                      ve.error_dict['records'][0]):  # type: ignore
                        err = dict({
                            k: [_("This record already exists")]
                            for k in pk_fields
                        }, **err)
                    elif (
                      'constraint_info' in ve.error_dict):
                        error_summary = _render_recombinant_constraint_errors(
                            lc, ve, chromo, 'upsert')
                    else:
                        log.warning('Failed to create %s record for org %s:\n%s',
                                    resource_name, owner_org, traceback.format_exc())
                        error_summary = _('Something went wrong, your record '
                                          'was not created. Please contact support.')
            # type_ignore_reason: incomplete typing
            elif ve.error_dict.get(
                    'info', {}).get('pgcode', '') == '23505':  # type: ignore
                err = dict({
                    k: [_("This record already exists")]
                    for k in pk_fields
                }, **err)
            else:
                log.warning('Failed to create %s record for org %s:\n%s',
                            resource_name, owner_org, traceback.format_exc())
                error_summary = _('Something went wrong, your record '
                                  'was not created. Please contact support.')
            if 'error' not in return_dict:
                return_dict['error'] = {}
            return_dict['error']['row_{}'.format(offset)] = {
                '__type': 'Validation Error',
                'message': error_summary,
                'data': err}
            return_dict['success'] = False
            offset += 1
        except Exception as e:
            return_dict['error'] = {'__type': 'Internal Server Error',
                                    'message': _('Internal Server Error')}
            return_dict['success'] = False
            log.warning(e)
            return _finish(500, return_dict, content_type='json')

    if 'error' in return_dict:
        return _finish(409, return_dict, content_type='json')

    return _finish_ok(return_dict)


@recombinant.route('/recombinant-refresh/<resource_name>/<owner_org>',
                   methods=['GET', 'POST'])
def refresh_dataset(resource_name: str, owner_org: str) -> Union[str, Response]:
    if not is_sysadmin(g.user):
        return abort(403)
    if request.method != 'POST':
        # handle page refreshes
        h.flash_notice(_('Form not submitted, please try again.'))
        return h.redirect_to('recombinant.preview_table',
                             resource_name=resource_name,
                             owner_org=owner_org)
    if 'refresh' in request.form:
        dataset_id = request.form['dataset_id']
        if not dataset_id:
            h.flash_error(_('Could not determine dataset to update.'))
        else:
            lc = LocalCKAN()
            dataset_dict = lc.action.package_show(id=dataset_id)
            for res in dataset_dict['resources']:
                if not h.check_access('datastore_delete',
                                      {'resource_id': res['id'],
                                       'filters': {}}):
                    return abort(403, _('User {0} not authorized '
                                        'to update resource {1}'.format(
                                            str(g.user), res['id'])))
            try:
                lc.action.recombinant_update(
                    owner_org=dataset_dict['organization']['name'],
                    dataset_type=dataset_dict['type'],
                    dataset_id=dataset_id,
                    force_update=True)
                h.flash_success(_('Resources successfully refreshed.'))
            except Exception:
                h.flash_error(_(
                    'Unable to regenerate the resources. Please contact '
                    '<a href="mailto:{support}">'
                    '{support}</a> for assistance.').format(
                        support=h.support_email_address()),
                    allow_html=True)
    return h.redirect_to(
        'recombinant.preview_table',
        resource_name=resource_name,
        owner_org=owner_org)


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

    bad_types: List[str] = h.recombinant_get_types()
    bad_types.remove(dataset['type'])
    bad_sheet_names = []
    for bt in bad_types:
        brs = get_geno(bt).get('resources', [])
        bad_sheet_names += [br['resource_name'] for br in brs]

    # type_ignore_reason: incomplete typing
    upload_data = read_excel(upload_file, expected_sheet_names.keys(),  # type: ignore
                             bad_sheet_names)
    total_records = 0
    # type_ignore_reason: incomplete typing
    backend: DatastorePostgresqlBackend = DatastoreBackend.\
        get_active_backend()  # type: ignore
    ds_write_connection = backend._get_write_engine().connect()
    ds_write_transaction = ds_write_connection.begin()
    try:
        while True:
            try:
                sheet_name, org_name, column_names, rows, method = next(upload_data)
            except StopIteration:
                break
            except BadExcelData as e:
                raise e
            except Exception as e:
                log.info('Unexpected error while uploading Recombinant file:')
                log.info(e)
                # unfortunately this can fail in all sorts of ways
                if asbool(config.get('debug', False)):
                    # on debug we want the real error
                    raise
                raise BadExcelData(
                    _("The server encountered a problem processing the file "
                      "uploaded. Please try copying your data into the latest "
                      "version of the template and uploading again. If this "
                      "problem continues, send your Excel file to "
                      "{support} so we may investigate.").format(
                          support=h.support_email_address()))

            if sheet_name not in expected_sheet_names:
                raise BadExcelData(_('Invalid file for this data type. ' +
                                     'Sheet must be labeled "{0}", ' +
                                     'but you supplied a sheet labeled "{1}"').format(
                                        '"/"'.join(sorted(expected_sheet_names)),
                                        sheet_name))

            if not h.check_access('datastore_upsert',
                                  {'resource_id': expected_sheet_names[sheet_name]}):
                return abort(403, _('User {0} not authorized to '
                                    'update resource {1}').format(
                                        str(g.user), expected_sheet_names[sheet_name]))

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
            if method == 'update':
                expected_columns = ['_id'] + expected_columns
                pk = ['_id']
            else:
                pk = chromo.get('datastore_primary_key', [])

            if column_names != expected_columns:
                raise BadExcelData(
                    _("This template is out of date. "
                      "Please try copying your data into the latest "
                      "version of the template and uploading again. If this "
                      "problem continues, send your Excel file to "
                      "{support} so we may investigate.").format(
                          support=h.support_email_address()))

            choice_fields = {
                f['datastore_id']:
                    'full' if f.get('excel_full_text_choices') else True
                for f in chromo['fields']
                if ('choices' in f or 'choices_file' in f)}

            records = get_records(
                rows,
                ([{'datastore_id': '_id', 'datastore_type': 'int'}]
                    if method == 'update' else [])
                + [f for f in chromo['fields'] if f.get(
                    'import_template_include', True) and not f.get(
                        'published_resource_computed_field')],
                pk,
                choice_fields)
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
                    pgerror = e.error_dict['errors'][  # type: ignore
                        'foreign_constraint'][0]
                elif 'info' in e.error_dict:
                    # because, where else would you put the error text?
                    # XXX improve this in datastore, please
                    # type_ignore_reason: incomplete typing
                    pgerror = e.error_dict['info']['orig'][0].decode(  # type: ignore
                        'utf-8')
                elif 'fields' in e.error_dict:
                    # type_ignore_reason: incomplete typing
                    pgerror = e.error_dict['fields'][0]  # type: ignore
                    key = re.search(KEY_ERROR_MATCH, str(pgerror))
                    if key:
                        key = key.group(1)
                    else:
                        key = _('unknown')
                    raise RecombinantFieldError(key)
                elif 'records' in e.error_dict:
                    # type_ignore_reason: incomplete typing
                    pgerror = e.error_dict['records'][0]  # type: ignore
                elif 'key' in e.error_dict:
                    # type_ignore_reason: incomplete typing
                    pgerror = e.error_dict['key'][0]  # type: ignore
                else:
                    pgerror = e.error_dict

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
    orig_errmsg = exception.error_dict['errors'][  # type: ignore
        'foreign_constraint'][0]
    foreign_error = chromo.get(
        'datastore_constraint_errors', {}).get(action)
    fk_err_template = chromo.get(
        'datastore_constraint_error_templates', {}).get(action)
    if foreign_error and not fk_err_template:
        error_message = _parse_constraint_error_from_psql_error(
            exception, foreign_error)['errors'][
                'foreign_constraint'][0]
    elif fk_err_template:
        ref_res_dict = lc.action.resource_show(
            # type_ignore_reason: incomplete typing
            id=exception.error_dict['constraint_info']['ref_resource'])  # type: ignore
        ref_pkg_dict = lc.action.package_show(
            id=ref_res_dict['package_id'])
        dt_query = {}
        # type_ignore_reason: incomplete typing
        _ref_keys = exception.error_dict['constraint_info'][  # type: ignore
            'ref_keys'].replace(' ', '').split(',')
        # type_ignore_reason: incomplete typing
        _ref_values = exception.error_dict['constraint_info'][  # type: ignore
            'ref_values'].replace(' ', '').split(',')
        for _i, key in enumerate(_ref_keys):
            dt_query[key] = _ref_values[_i]
        dt_query = json.dumps(dt_query, separators=(',', ':'))
        error_message = render(
            fk_err_template,
            extra_vars=dict(
                # type_ignore_reason: incomplete typing
                exception.error_dict['constraint_info'],  # type: ignore
                ref_resource=ref_res_dict,
                ref_dataset=ref_pkg_dict,
                dt_query=dt_query))
    else:
        error_message = orig_errmsg
    return error_message


def _get_choice_fields(resource_name: str,
                       data: Optional[Dict[str, Any]] = None,
                       org_name: Optional[str] = None) -> Dict[str, Any]:
    separator = ' : ' if h.lang() == 'fr' else ': '
    choice_fields = {}
    for datastore_id, choices in h.recombinant_choice_fields(
      resource_name, org_name=org_name).items():
        available_keys = []
        f = h.recombinant_get_field(resource_name, datastore_id)
        form_choices_prefix_code = f.get('form_choices_prefix_code', False)
        form_choice_keys_only = f.get('form_choice_keys_only', False)
        if datastore_id not in choice_fields:
            choice_fields[datastore_id] = []
        # allow for suffixes to labels. If the value has the suffix, add
        # the suffix labels.
        suffix = None
        suffix_label = ''
        for _suffix, _labels in f.get('choices_suffix_filter', {}).items():
            suffix = _suffix
            suffix_label = _labels[h.lang()]
        for (k, v) in choices:
            available_keys.append(k)
            if suffix and k.endswith(suffix):
                v += ' %s' % suffix_label
            if form_choice_keys_only:
                choice_fields[datastore_id].append({'value': k,
                                                    'label': k})
                continue
            elif form_choices_prefix_code:
                choice_fields[datastore_id].append({'value': k,
                                                    'label': k + separator + v})
                continue
            choice_fields[datastore_id].append({'value': k,
                                                'label': v})
        # support current data that may not be in the choices anymore
        if data and data.get(datastore_id):
            _current_val = data[datastore_id]
            if isinstance(_current_val, str):
                # support multi choice
                _current_val = [_current_val]
            for _v in _current_val:
                if _v in available_keys:
                    continue
                _l = _v
                if suffix and _l.endswith(suffix):
                    # we don't have any other labels at this point,
                    # so can only use the suffix label
                    _l = suffix_label
                if form_choice_keys_only:
                    choice_fields[datastore_id].append({'value': _v,
                                                        'label': _v})
                    continue
                elif form_choices_prefix_code:
                    choice_fields[datastore_id].append({'value': _v,
                                                        'label': _v + separator + _l})
                    continue
                choice_fields[datastore_id].append({'value': _v,
                                                    'label': _l})
    return choice_fields


def _url_part_unescape(urlpart: str) -> str:
    """
    reverse url_part_escape
    """
    return ''.join(
        codecs.decode(s, 'hex').decode('utf-8') if i % 2 else s
        for i, s in enumerate(urlpart.split('_'))
    )


def _clean_check_type_errors(post_data: Dict[str, Any],
                             fields: List[Dict[str, Any]],
                             pk_fields: List[str],
                             choice_fields: Dict[str, Any]) -> \
                                Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    clean posted data and check type errors, add type error messages
    to errors dict returned. This is required because type errors on any
    field prevent triggers from running so we don't get any other errors
    from the datastore_upsert call.
    :param post_data: form data
    :param fields: recombinant fields
    :param pk_fields: list of primary key field ids
    :param choice_fields: {field id: choices, ...}
    :return: cleaned data, errors
    """
    data = {}
    err = {}

    for f in fields:
        f_id = f['datastore_id']
        if (
          not f.get('import_template_include', True) or
          f.get('published_resource_computed_field', False)):
            continue
        else:
            val = post_data.get(f['datastore_id'], '')
            if isinstance(val, list):
                val = ','.join(val)
            val = canonicalize(
                val,
                f['datastore_type'],
                primary_key=f['datastore_id'] in pk_fields,
                choice_field=f_id in choice_fields)
            if val:
                if f['datastore_type'] in ('money', 'numeric'):
                    try:
                        decimal.Decimal(val)
                    except decimal.InvalidOperation:
                        err[f['datastore_id']] = [_('Number required')]
                elif f['datastore_type'] == 'int':
                    try:
                        int(val)
                    except ValueError:
                        err[f['datastore_id']] = [_('Integer required')]
            data[f['datastore_id']] = val

    return data, err


def _normalize_record_newlines(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalizes newline characters to \\n
    """
    return dict((k, v.replace('\r\n', '\n').replace('\r', '\n')
                 if isinstance(v, str) else v)
                for k, v in record.items())


@recombinant.route('/datatable/<resource_name>/<resource_id>',
                   methods=['GET', 'POST'])
@csrf.exempt
def datatable(resource_name: str, resource_id: str) -> Union[str, Response]:
    params = parse_params(request.form)
    # type_ignore_reason: datatable param draw is int
    draw = int(params['draw'])  # type: ignore
    search_text = str(params['search[value]'])
    # type_ignore_reason: datatable param start is int
    offset = int(params['start'])  # type: ignore
    # type_ignore_reason: datatable param length is int
    limit = int(params['length']) if params['length'] else 15  # type: ignore
    is_edit_mode = asbool(params['is_edit_mode'])

    chromo = get_chromo(resource_name)
    lc = LocalCKAN(username=g.user)
    try:
        unfiltered_response = lc.action.datastore_search(
            resource_id=resource_id,
            limit=1,
        )
    except NotAuthorized:
        # datatables js can't handle any sort of error response
        # return no records instead
        return json.dumps({
            'draw': draw,
            'iTotalRecords': -1,  # with a hint that something is wrong
            'iTotalDisplayRecords': -1,
            'aaData': [],
        })

    can_edit = h.check_access('resource_update', {'id': resource_id})
    cols = []
    fids = []
    for f in chromo['fields']:
        if f.get('published_resource_computed_field', False):
            continue
        cols.append(f['datastore_id'])
        fids.append(f['datastore_id'])
    # Select | (Edit) | ...
    prefix_cols = 2 if chromo.get('edit_form', False) and can_edit else 1

    sort_list = []
    i = 0
    while True:
        if 'order[%d][column]' % i not in params:
            break
        # type_ignore_reason: datatable param 'order[%d][column] is int
        sort_by_num = int(params['order[%d][column]' % i])  # type: ignore
        sort_order = (
            'desc' if params['order[%d][dir]' % i] == 'desc'
            else 'asc')
        sort_list.append(
            cols[sort_by_num - prefix_cols] + ' ' + sort_order + ' nulls last')
        i += 1

    col_filters = {}
    i = 0
    while True:
        if 'columns[%d][search][value]' % i not in request.form:
            break
        try:
            v = json.loads(request.form['columns[%d][search][value]' % i])
        except (ValueError, KeyError):
            v = str(request.form['columns[%d][search][value]' % i])
        if v:
            k = str(request.form['columns[%d][name]' % i])
            col_filters[k] = v
        i += 1

    if is_edit_mode:
        offset = 0
        limit = MAX_INT

    if is_edit_mode and not col_filters:
        response = {}
    else:
        response = lc.action.datastore_search(
            q=search_text,
            resource_id=resource_id,
            offset=offset,
            limit=limit,
            sort=', '.join(sort_list),
            filters=col_filters)

    if is_edit_mode and not col_filters:
        default_fill = chromo.get('datatables_default_fill', 10)
        aadata = [
            [''] +  # Expand column
            ['<input type="checkbox">'] +  # Select column
            ['' for _col in cols] for _row in range(default_fill)]
    else:
        aadata = [
            [''] +  # Expand column
            ['<input type="checkbox">'] +  # Select column
            [row.get(col, '') for col in cols] for row in response['records']]

    return json.dumps({
        'draw': draw,
        'iTotalRecords': unfiltered_response.get('total', 0),
        'iTotalDisplayRecords': response.get('total', 0),
        'aaData': aadata,
    })


# TODO: DEPRECATED: REMOVE AFTER FULL PD DATATABLES QA
@recombinant.route('/datatable_depr/<resource_name>/<resource_id>',
                   methods=['GET', 'POST'])
@csrf.exempt
def datatable_depr(resource_name: str, resource_id: str) -> Union[str, Response]:
    params = parse_params(request.form)
    # type_ignore_reason: datatable param draw is int
    draw = int(params['draw'])  # type: ignore
    search_text = str(params['search[value]'])
    dt_query = str(params['dt_query'])
    if dt_query and not search_text:
        search_text = dt_query
    # type_ignore_reason: datatable param start is int
    offset = int(params['start'])  # type: ignore
    # type_ignore_reason: datatable param length is int
    limit = int(params['length'])  # type: ignore

    chromo = get_chromo(resource_name)
    lc = LocalCKAN(username=g.user)
    try:
        unfiltered_response = lc.action.datastore_search(
            resource_id=resource_id,
            limit=1,
        )
    except NotAuthorized:
        # datatables js can't handle any sort of error response
        # return no records instead
        return json.dumps({
            'draw': draw,
            'iTotalRecords': -1,  # with a hint that something is wrong
            'iTotalDisplayRecords': -1,
            'aaData': [],
        })

    can_edit = h.check_access('resource_update', {'id': resource_id})
    cols = []
    fids = []
    for f in chromo['fields']:
        if f.get('published_resource_computed_field', False):
            continue
        cols.append(f['datastore_id'])
        fids.append(f['datastore_id'])
    # Select | (Edit) | ...
    prefix_cols = 2 if chromo.get('edit_form', False) and can_edit else 1

    sort_list = []
    i = 0
    while True:
        if 'order[%d][column]' % i not in params:
            break
        # type_ignore_reason: datatable param 'order[%d][column] is int
        sort_by_num = int(params['order[%d][column]' % i])  # type: ignore
        sort_order = (
            'desc' if params['order[%d][dir]' % i] == 'desc'
            else 'asc')
        sort_list.append(
            cols[sort_by_num - prefix_cols] + ' ' + sort_order + ' nulls last')
        i += 1

    response = lc.action.datastore_search(
        q=search_text,
        resource_id=resource_id,
        offset=offset,
        limit=limit,
        sort=', '.join(sort_list),
    )

    aadata = [
        ['<input type="checkbox">'] +
        [datatablify(row.get(colname, ''), colname, chromo) for colname in cols]
        for row in response['records']]

    if chromo.get('edit_form', False) and can_edit:
        res = lc.action.resource_show(id=resource_id)
        pkg = lc.action.package_show(id=res['package_id'])
        pkids = [fids.index(k) for k in aslist(chromo['datastore_primary_key'])]
        for row in aadata:
            row.insert(1, (
                    '<a href="{0}" aria-label="' + _("Edit") + '">'
                    '<i class="fa fa-lg fa-edit" aria-hidden="true"></i></a>').format(
                    h.url_for(
                        'recombinant.update_record',
                        owner_org=pkg['organization']['name'],
                        resource_name=resource_name,
                        pk=','.join(_url_part_escape(row[i+1]) for i in pkids)
                    )
                )
            )

    return json.dumps({
        'draw': draw,
        'iTotalRecords': unfiltered_response.get('total', 0),
        'iTotalDisplayRecords': response.get('total', 0),
        'aaData': aadata,
    })


# TODO: DEPRECATED: REMOVE AFTER FULL PD DATATABLES QA
def _url_part_escape(orig: str) -> str:
    """
    simple encoding for url-parts where all non-alphanumerics are
    wrapped in e.g. _xxyyzz_ blocks w/hex UTF-8 xx, yy, zz values

    used for safely including arbitrary unicode as part of a url path
    all returned characters will be in [a-zA-Z0-9_-]
    """
    return '_'.join(
        codecs.encode(s.encode('utf-8'), 'hex').decode('ascii') if i % 2 else s
        for i, s in enumerate(
            re.split(r'([^-a-zA-Z0-9]+)', orig)
        )
    )


# TODO: DEPRECATED: REMOVE AFTER FULL PD DATATABLES QA
def datatablify(v: Any, colname: str, chromo: Dict[str, Any]) -> str:
    '''
    format value from datastore v for display in a datatable preview
    '''
    chromo_field = None
    for f in chromo['fields']:
        if f['datastore_id'] == colname:
            chromo_field = f
            break
    if v is None:
        return ''
    if v is True:
        return 'TRUE'
    if v is False:
        return 'FALSE'
    if isinstance(v, list):
        return ', '.join(str(e) for e in v)
    if colname in ('record_created', 'record_modified') and v:
        return _date_str_to_datetime(v).replace(tzinfo=utc).astimezone(
            this_tz).strftime('%Y-%m-%d %H:%M:%S %Z')
    if chromo_field and chromo_field.get('datastore_type') == 'money':
        if isinstance(v, str) and '$' in v:
            return v
        return '${:,.2f}'.format(v)
    return str(v)


# copied from ckan 2.6 branch
# https://github.com/open-data/ckan
# /blob/ee0a94c97f8988e78c9b1f92f92adb5c26884841/ckan/lib/helpers.py#L1245
def _date_str_to_datetime(date_str: str) -> 'datetime.datetime':
    '''
    Convert ISO-like formatted datestring to datetime object.

    This function converts ISO format date- and datetime-strings into
    datetime objects.  Times may be specified down to the microsecond.  UTC
    offset or timezone information may **not** be included in the string.
    Note - Although originally documented as parsing ISO date(-times), this
           function doesn't fully adhere to the format.  This function will
           throw a ValueError if the string contains UTC offset information.
           So in that sense, it is less liberal than ISO format.  On the
           other hand, it is more liberal of the accepted delimiters between
           the values in the string.  Also, it allows microsecond precision,
           despite that not being part of the ISO format.
    '''

    time_tuple = re.split(r'[^\d]+', date_str, maxsplit=5)

    # Extract seconds and microseconds
    if len(time_tuple) >= 6:
        m = re.match(r'(?P<seconds>\d{2})(\.(?P<microseconds>\d+))?$',
                     time_tuple[5])
        if not m:
            raise ValueError('Unable to parse %s as seconds.microseconds' %
                             time_tuple[5])
        seconds = int(m.groupdict()['seconds'])
        microseconds = int((str(m.groupdict(0).get('microseconds')) + '00000')[0:6])
        time_tuple = time_tuple[:5] + [seconds, microseconds]

    # type_ignore_reason: typchecker can't guess number of arguments
    return datetime.datetime(*map(int, time_tuple))  # type: ignore
