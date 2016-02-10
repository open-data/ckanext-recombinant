
class IRecombinant(p.Interface):
    pass

def _get_tables():
    """
    Find the RecombinantPlugin instance and get the
    table configuration from it
    """
    for plugin in p.PluginImplementations(IRecombinant):
        return plugin._tables

def _get_dataset_types():
    for plugin in p.PluginImplementations(_IRecombinant):
        return plugin._dataset_types
    

def get_table(sheet_name):
    """
    Get the table configured with the input dataset type
    """
    tables = _get_tables()
    for t in tables:
        if t['sheet_name'] == sheet_name:
            break
    else:
        raise RecombinantException('sheet_name "%s" not found'
            % dataset_type)
    return t

def get_dataset_type(sheet_name):
    """
    Get the table configured with the input dataset type
    """
    tables = _get_tables()
    for t in tables:
        if t['sheet_name'] == sheet_name:
            break
    else:
        raise RecombinantException('sheet_name "%s" not found'
            % dataset_type)
    return t

def get_target_datasets():
    """
    Find the RecombinantPlugin instance and get its
    configured target datasets (e.g., ['ati', 'pd', ...])
    """
    tables = _get_tables()
    return list(set((t['target_dataset'] for t in tables)))


def get_sheet_names(target_dataset):
    """
    Find the RecombinantPlugin instance and get its
    configured sheet names for the input target dataset
    """
    tables = _get_tables()
    return [t['sheet_name'] for t in tables
        if t['target_dataset'] == target_dataset]


