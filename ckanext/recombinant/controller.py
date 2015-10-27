from pylons.i18n import _
from pylons import config
from paste.deploy.converters import asbool

from ckan.lib.base import (c, render, model, request, h, g,
    response, abort, redirect)
from ckan.controllers.package import PackageController
from ckanext.recombinant.read_xls import read_xls, get_records
from ckanext.recombinant.write_xls import xls_template
from ckanext.recombinant.commands import _get_tables
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
        try:
            lc = ckanapi.LocalCKAN(username=c.user)
            package = lc.action.package_show(id=id)
            owner_org = package['organization']['name']

            if request.POST['xls_update'] == u'':
                msg = _('You must provide a valid file')
                raise ValidationError({'xls_update': msg})

            sheet_name, org_name, date_mode = None, None, None
            try:
                upload_data = read_xls(
                    '',
                    file_contents=request.POST['xls_update'].file.read())
                sheet_name, org_name, date_mode = next(upload_data)
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

            # is this the right sheet for this organization?
            if org_name != owner_org:
                msg = _(
                    'Invalid sheet for this organization. ' +
                    'Sheet must be labeled for {0}, ' +
                    'but you supplied a sheet for {1}').format(
                        owner_org, org_name)
                raise ValidationError(
                    {'xls_update': msg})

            for t in _get_tables():
                if t['xls_sheet_name'] == sheet_name:
                    break
            else:
                msg = _(
                    "Sheet name '{0}' " +
                    "not found in list of valid tables").format(sheet_name)
                raise ValidationError({'xls_update': msg})

            resource_id = package['resources'][0]['id']

            records = get_records(upload_data, t['fields'], date_mode)

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

    def template(self, id):
        lc = ckanapi.LocalCKAN(username=c.user)
        dataset = lc.action.package_show(id=id)
        org = lc.action.organization_show(
            id=dataset['owner_org'],
            include_datasets=False)

        book = xls_template(dataset['type'], org)
        blob = StringIO()
        book.save(blob)
        response.headers['Content-Type'] = 'application/vnd.ms-excel'
        response.headers['Content-Disposition'] = (
            'inline; filename="{0}.{1}.xls"'.format(
                dataset['organization']['name'],
                dataset['type']))
        return blob.getvalue()

