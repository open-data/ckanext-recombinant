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
    if data_dict.get(u'type') in h.recombinant_get_types():
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
    if data_dict.get(u'type') in h.recombinant_get_types():
        dataset_type = data_dict.get(u'type')
        owner_org = Group.get(data_dict.get(u'owner_org'))
        lc = LocalCKAN(username=context['user'])
        result = lc.action.package_search(
            q="type:%s AND organization:%s" % (dataset_type, owner_org.name),
            include_private=True,
            rows=2)
        if result['results']:
            raise ValidationError({'owner_org':
                _("dataset type %s already exists for this organization")
                % dataset_type})
    return up_func(context, data_dict)
