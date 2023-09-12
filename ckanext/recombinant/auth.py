from ckan.plugins.toolkit import chained_auth_function, h, _
from ckan.model.group import Group
from ckanapi import LocalCKAN, ValidationError


@chained_auth_function
def package_update(up_func, context, data_dict):
    """
    Recombinant packages and resources should not be
    editable by users after they have been made.

    Affects update, patch, and delete.
    """
    if data_dict and data_dict.get(u'type') in h.recombinant_get_types():
        return {'success': False,
                'msg': _('User %s not authorized to modify Recombinant type: %s') %
                            (str(context[u'user']), data_dict.get(u'type'))}
    return up_func(context, data_dict)


@chained_auth_function
def package_create(up_func, context, data_dict):
    """
    If the user has permissions to create packages, they should still
    be allowed to create the Recombinant packages and resources.

    However, users should not be allowed to create multiple packages
    of the same type for a single organization.
    """
    if data_dict and data_dict.get(u'type') in h.recombinant_get_types():
        return {'success': False,
                'msg': _('User %s not authorized to create Recombinant packages: %s') %
                            (str(context[u'user']), data_dict.get(u'type'))}
    return up_func(context, data_dict)
