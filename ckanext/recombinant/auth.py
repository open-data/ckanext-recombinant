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


@chained_auth_function
def datastore_delete(up_func, context, data_dict):
    """
    Users should not be able to delete a Datestore table for
    Recombinant types. We only want them to be able to delete rows.
    """
    res = context['model'].Resource.get(data_dict.get('resource_id'))
    pkg = context['model'].Package.get(getattr(res, 'package_id', None))
    if not res or not pkg or pkg.type not in h.recombinant_get_types():
        return up_func(context, data_dict)
    if 'filters' not in data_dict:
        # if there are no filters, the Datastore table will be deleted.
        # we do not want that to happen for Recombinant types.
        return {'success': False,
                'msg': _("Cannot delete Datastore for type: %s. "
                         "Use datastore_records_delete instead.")
                         % pkg.type}
    return up_func(context, data_dict)
