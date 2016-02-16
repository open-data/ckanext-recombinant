import ckan.plugins as p

from ckanext.recombinant.errors import RecombinantException


class IRecombinant(p.Interface):
    pass


def _get_plugin():
    """
    Find the RecombinantPlugin instance
    """
    for plugin in p.PluginImplementations(IRecombinant):
        return plugin
    raise RecombinantException(
        'Recombinant plugin not found. Have you enabled the plugin?')


def get_table(sheet_name):
    """
    Get the table for the given sheet
    """
    tables = _get_plugin()._tables
    try:
        return tables[sheet_name]
    except KeyError:
        raise RecombinantException('sheet_name "%s" not found'
            % sheet_name)


def get_dataset_type(dataset_type):
    """
    Get the config for the given dataset type
    """
    dataset_types = _get_plugin()._dataset_types
    try:
        return dataset_types[dataset_type]
    except KeyError:
        raise RecombinantException('dataset_type "%s" not found'
            % dataset_type)


def get_dataset_types():
    """
    Get a list of recombinant dataset types
    """
    return sorted(_get_plugin()._dataset_types)


def get_target_datasets():
    """
    Find the RecombinantPlugin instance and get its
    configured target datasets (e.g., ['ati', 'pd', ...])
    """
    tables = _get_plugin()._dataset_types
    return sorted((t['target_dataset'] for t in tables.values()))


def get_sheet_names(target_dataset):
    """
    Find the RecombinantPlugin instance and get its
    configured sheet names for the input target dataset
    """
    tables = _get_plugin()._dataset_types
    return [r['sheet_name']
        for t in tables
        for r in t['resources']
        if t['target_dataset'] == target_dataset]


