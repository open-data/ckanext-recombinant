from ckan.lib.base import (c, render, model, request, h, g,
    response, abort, redirect)
from ckan.controllers.package import PackageController
from ckanext.recombinant.read_xls import read_xls
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
                
            redirect(h.url_for(controller='package',
                               action='read', id=id))
        except ValidationError, e:
            #import pdb; pdb.set_trace()
            vars = {'errors': e.error_dict,
                    'error_summary': e.error_summary, 'action': 'edit'}
            return render(self._edit_template(package_type), extra_vars = vars)