from ckan.lib.base import (c, render, model, request, h, g,
    response, abort, redirect)
from ckan.controllers.package import PackageController
from ckanext.recombinant.read_xls import read_xls
from ckanext.recombinant.commands import _get_tables
from ckan.model import *
from ckan.logic import ValidationError

import ckanapi

class UploadController(PackageController):
    
    def upload(self, id):
        package_type = self._get_package_type(id)
        try:
            if request.POST['xls_update'] == u'':
                raise ValidationError({'xls_update': 'You must provide a valid file'})
            
            upload_data = read_xls('', file_contents = request.POST['xls_update'].file.read())
            sheet_name, org_name = next(upload_data)
        
            lc = ckanapi.LocalCKAN(username = c.user)
            package = lc.action.package_show(id = id)
            owner_org = lc.action.organization_show(id = package['owner_org'])['name']
        
            #is this the right sheet for this organization?
            if org_name != owner_org:
                msg = ('Invalid sheet for this organization. Sheet must be labeled for{0}, ' + 
                       'but you supplied a sheet for {1}').format(owner_org, org_name)
                raise ValidationError({'xls_update': msg})
                
            for t in _get_tables():
                if t['xls_sheet_name'] == sheet_name:
                    break
            else:
                msg = "Sheet name '{0}' not found in list of valid tables".format(sheet_name)
                raise ValidationError({'xls_update': msg})
                
            resource_id = package['resources'][0]['id']
            
            records = []
            fields = t['datastore_table']['fields']
            for n, row in enumerate(upload_data):
                if len(row) != len(fields): 
                    msg = ("Row {0} of this sheet has {1} columns, "
                            "expecting {2}").format(n+3, len(row), len(fields))
                    raise ValidationError({'xls_update': msg})
        
                records.append(dict(
                    (f['id'], v) for f, v in zip(fields, row)))
                    
            lc.action.datastore_upsert(resource_id=resource_id, records=records)
            
            redirect(h.url_for(controller='package',
                               action='read', id=id))
        except ValidationError, e:
            errors = []
            for error in e.error_dict.values():
                errors.append(str(error).decode('utf-8'))
            vars = {'errors': errors, 'action': 'edit'}
            return render(self._edit_template(package_type), extra_vars = vars)