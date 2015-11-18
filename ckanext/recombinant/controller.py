from pylons.i18n import _
from pylons import config
from paste.deploy.converters import asbool

from ckan.lib.base import (c, render, model, request, h, g,
    response, abort, redirect)
from ckan.controllers.package import PackageController
from ckanext.recombinant.read_xls import read_xls, get_records
from ckanext.recombinant.write_xls import xls_template
from ckanext.recombinant.plugins import get_table, primary_key_fields
from ckan.logic import ValidationError, NotAuthorized

from cStringIO import StringIO

import ckanapi


class UploadController(PackageController):
    """
    Controller for downloading Excel templates and
    uploading packages via Excel .xls files
    """

    def upload(self, id):
        package_type = self._get_package_type(id)
        t = get_table(package_type)
        expected_sheet_name = t['xls_sheet_name']

        try:
            lc = ckanapi.LocalCKAN(username=c.user)
            package = lc.action.package_show(id=id)
            owner_org = package['organization']['name']

            if request.POST['xls_update'] == u'':
                msg = _('You must provide a valid file')
                raise ValidationError({'xls_update': msg})

            upload_data = read_xls(request.POST['xls_update'].file)
            sheet_name, org_name = None, None
            try:
                sheet_name, org_name = next(upload_data)
            except:
                # XXX bare except because this can fail in all sorts of ways
                if asbool(config.get('debug', False)):
                    # on debug we want the real error
                    raise
                raise ValidationError({'xls_update':
                    _("The server encountered a problem processing the file "
                    "uploaded. Please try copying your data into the latest "
                    "version of the template and uploading again. If this "
                    "problem continues, send your Excel file to "
                    "open-ouvert@tbs-sct.gc.ca so we may investigate.")})

            if expected_sheet_name != sheet_name:
                raise ValidationError({'xls_update':
                    _('Invalid file for this data type. ' +
                    'Sheet must be labeled "{0}", ' +
                    'but you supplied a sheet labeled "{1}"').format(
                        expected_sheet_name, sheet_name)})

            # is this the right sheet for this organization?
            if org_name != owner_org:
                msg = _(
                    'Invalid sheet for this organization. ' +
                    'Sheet must be labeled for {0}, ' +
                    'but you supplied a sheet for {1}').format(
                        owner_org, org_name)
                raise ValidationError(
                    {'xls_update': msg})

            resource_id = package['resources'][0]['id']

            records = get_records(upload_data, t['fields'])

            method = 'upsert' if t.get('datastore_primary_key') else 'insert'
            try:
                lc.action.datastore_upsert(
                    method=method,
                    resource_id=resource_id,
                    records=records)
            except NotAuthorized, na:
                msg = _(
                    'You do not have permission to upload to {0}').format(
                        owner_org)
                raise ValidationError({'xls_update': msg})

            h.flash_success(_(
                "Your file was successfully uploaded into the central system."
                ))

            redirect(h.url_for(controller='package', action='read', id=id))
        except ValidationError, e:
            x_vars = {'errors': e.error_dict.values(), 'action': 'edit'}
            c.pkg_dict = package
            return render(self._edit_template(package_type), extra_vars=x_vars)

    def delete_record(self, id):
        lc = ckanapi.LocalCKAN(username=c.user)
        filters = {}
        package_type = self._get_package_type(id)
        for f in primary_key_fields(package_type):
           filters[f['datastore_id']] = request.POST.get(f['datastore_id'], '')

        package = lc.action.package_show(id=id)
        result = lc.action.datastore_search(
            resource_id=package['resources'][0]['id'],
            filters=filters,
            rows=2)  # only need two to know if there are multiple matches
        records = result['records']

        x_vars = {'filters': filters, 'action': 'edit'}
        if not records:
            x_vars['delete_errors'] = [_('No matching records found')]
        elif len(records) > 1:
            x_vars['delete_errors'] = [_('Multiple matching records found')]

        if 'delete_errors' in x_vars:
            c.pkg_dict = package
            return render(self._edit_template(package_type), extra_vars=x_vars)

        # XXX: can't avoid the race here with the existing datastore API.
        # datastore_delete doesn't support _id filters
        lc.action.datastore_delete(
            resource_id=package['resources'][0]['id'],
            filters=filters,
            )
        h.flash_success(_(
            "Record deleted."
            ))

        redirect(h.url_for(controller='package', action='read', id=id))


    def template(self, id):
        lc = ckanapi.LocalCKAN(username=c.user)
        dataset = lc.action.package_show(id=id)
        org = lc.action.organization_show(
            id=dataset['owner_org'],
            include_datasets=False)

        book = xls_template(dataset['type'], org)
        blob = StringIO()
        book.save(blob)
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        response.headers['Content-Disposition'] = (
            'inline; filename="{0}.{1}.xlsx"'.format(
                dataset['organization']['name'],
                dataset['type']))
        return blob.getvalue()

