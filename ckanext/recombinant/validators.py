from ckan.plugins.toolkit import _, h


def recombinant_foreign_keys(key, data, errors, context):
    """
    Limit to Recombinant Resources only.
    """
    resource_id = data[('resource_id',)]
    if not resource_id:
        resource_id = data[('id',)]
    res = context['model'].Resource.get(resource_id)
    pkg = context['model'].Package.get(getattr(res, 'package_id', None))
    if not res or not pkg or pkg.type not in h.recombinant_get_types():
        errors[key].append(
            _('Cannot assign foreign keys to a non-recombinant resource.'))
