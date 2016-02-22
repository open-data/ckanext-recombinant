"""
Dataset Definitions (chromo) and Resource Definitions (geno) are loaded
from files specified in the recombinant.definitions ini setting.

This module provides access to those definitions.
"""

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


def get_chromo(resource_name):
    """
    Get the resource definition (chromo) for the given resource name
    """
    chromos = _get_plugin()._chromos
    try:
        return chromos[resource_name]
    except KeyError:
        raise RecombinantException('resource_name "%s" not found'
            % sheet_name)


def get_geno(dataset_type):
    """
    Get the dataset definition (geno) for the given dataset type
    """
    genos = _get_plugin()._genos
    try:
        return genos[dataset_type]
    except KeyError:
        raise RecombinantException('dataset_type "%s" not found'
            % dataset_type)


def get_dataset_types():
    """
    Get a list of recombinant dataset types
    """
    return sorted(_get_plugin()._genos)


def get_target_datasets():
    """
    Find the RecombinantPlugin instance and get its
    configured target datasets (e.g., ['ati', 'pd', ...])
    """
    genos = _get_plugin()._genos
    return sorted((t['target_dataset'] for t in genos.values()))
