from typing import Optional
from ckan.types import (
    AuthFunction,
    Context,
    DataDict,
    AuthResult
)

from ckan.plugins.toolkit import chained_auth_function, h, _


@chained_auth_function
def package_update(up_func: AuthFunction,
                   context: Context,
                   data_dict: Optional[DataDict]) -> AuthResult:
    """
    Recombinant packages and resources should not be
    editable by users after they have been made.

    Affects update, patch, and delete.
    """
    if data_dict and data_dict.get('type') in h.recombinant_get_types():
        return {'success': False,
                'msg': _('User %s not authorized to modify Recombinant type: %s') %
                        (str(context['user']), data_dict.get('type'))}
    # type_ignore_reason: incomplete typing
    return up_func(context, data_dict)  # type: ignore


@chained_auth_function
def package_create(up_func: AuthFunction,
                   context: Context,
                   data_dict: Optional[DataDict]) -> AuthResult:
    """
    If the user has permissions to create packages, they should still
    be allowed to create the Recombinant packages and resources.

    However, users should not be allowed to create multiple packages
    of the same type for a single organization.
    """
    if data_dict and data_dict.get('type') in h.recombinant_get_types():
        return {'success': False,
                'msg': _('User %s not authorized to create '
                         'Recombinant packages: %s') %
                        (str(context['user']), data_dict.get('type'))}
    # type_ignore_reason: incomplete typing
    return up_func(context, data_dict)  # type: ignore


@chained_auth_function
def datastore_delete(up_func: AuthFunction,
                     context: Context,
                     data_dict: Optional[DataDict]) -> AuthResult:
    """
    Users should not be able to delete a Datestore table for
    Recombinant types. We only want them to be able to delete rows.
    """
    if not data_dict:
        data_dict = {}
    res = context['model'].Resource.get(data_dict.get('resource_id', ''))
    pkg = context['model'].Package.get(getattr(res, 'package_id', None))
    if not res or not pkg or pkg.type not in h.recombinant_get_types():
        return up_func(context, data_dict)
    if 'filters' not in data_dict:
        # if there are no filters, the Datastore table will be deleted.
        # we do not want that to happen for Recombinant types.
        return {'success': False,
                'msg': _("Cannot delete Datastore for type: %s. "
                         "Use datastore_records_delete instead.") % pkg.type}
    return up_func(context, data_dict)
