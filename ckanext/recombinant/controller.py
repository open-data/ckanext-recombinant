from pylons.i18n import _

from ckan.lib.base import (c, render, model, request, h, g,
    response, abort, redirect)
from ckan.controllers.package import PackageController
from ckanext.recombinant.read_xls import read_xls, get_records
from ckanext.recombinant.write_xls import xls_template
from ckanext.recombinant.commands import _get_tables
from ckan.logic import ValidationError
import ckan.model

from cStringIO import StringIO

import ckanapi


class UploadController(PackageController):

    def upload(self, id):
        package_type = self._get_package_type(id)
        try:
            lc = ckanapi.LocalCKAN(username = c.user)
            package = lc.action.package_show(id = id)
            owner_org = package['organization']['name']

            if not (h.check_access('package_update', {'id': id})):
                raise ValidationError({'xls_update':
                    _('You do not have permission to upload to {0}').format(
                        owner_org)})

            if request.POST['xls_update'] == u'':
                raise ValidationError(
                    {'xls_update': _('You must provide a valid file')})

            upload_data = read_xls(
                '',
                file_contents = request.POST['xls_update'].file.read())
            sheet_name, org_name = next(upload_data)


            #is this the right sheet for this organization?
            if org_name != owner_org:
                msg = _('Invalid sheet for this organization. ' +
                    'Sheet must be labeled for {0}, ' +
                    'but you supplied a sheet for {1}').format(
                        owner_org,
                        org_name)
                raise ValidationError({'xls_update': msg})

            for t in _get_tables():
                if t['xls_sheet_name'] == sheet_name:
                    break
            else:
                msg = _("Sheet name '{0}' not found in list of valid tables"
                    ).format(sheet_name)
                raise ValidationError({'xls_update': msg})

            resource_id = package['resources'][0]['id']

            records = get_records(upload_data, t['fields'])
            lc.action.datastore_upsert(resource_id=resource_id, records=records)

            h.flash_success(_(
                "Your file was successfully uploaded into the central system."
                ))

            redirect(h.url_for(controller='package',
                               action='read', id=id))
        except ValidationError, e:
            errors = []
            for error in e.error_dict.values():
                errors.append(str(error).decode('utf-8'))
            vars = {'errors': errors, 'action': 'edit'}
            c.pkg_dict = package
            return render(self._edit_template(package_type), extra_vars = vars)

    def template(self, id):
        lc = ckanapi.LocalCKAN(username = c.user)
        dataset = lc.action.package_show(id=id)
        org = lc.action.organization_show(id=dataset['owner_org'],
            include_datasets=False)

        book = xls_template(dataset['type'], org)
        blob = StringIO()
        book.save(blob)
        response.headers['Content-Type'] = 'application/vnd.ms-excel'
        return blob.getvalue()

