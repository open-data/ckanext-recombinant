"""
Dataset Definitions (chromo) and Resource Definitions (geno) are loaded
from files specified in the recombinant.definitions ini setting.

This module provides access to those definitions.
"""
from typing import List, Dict, Optional, Any

import ckan.plugins as p

from ckanext.recombinant.errors import RecombinantException


class IRecombinant(p.Interface):
    _published_resource_ids = {}
    _genos = {}
    _chromos = {}

    pass


def _get_plugin():
    """
    Find the RecombinantPlugin instance
    """
    for plugin in p.PluginImplementations(IRecombinant):
        return plugin
    raise RecombinantException(
        'Recombinant plugin not found. Have you enabled the plugin?')


def get_chromo(resource_name: str) -> Dict[str, Any]:
    """
    Get the resource definition (chromo) for the given resource name
    """
    chromos = _get_plugin()._chromos
    try:
        return chromos[resource_name]
    except KeyError:
        # workaround for file names having -'s removed when uploaded
        # to some versions of CKAN
        for rname in chromos:
            if rname.replace('-', '') == resource_name:
                return chromos[rname]
        raise RecombinantException('resource_name "%s" not found' % resource_name)


def get_geno(dataset_type: str) -> Dict[str, Any]:
    """
    Get the dataset definition (geno) for the given dataset type
    """
    genos = _get_plugin()._genos
    try:
        return genos[dataset_type]
    except KeyError:
        raise RecombinantException('dataset_type "%s" not found' % dataset_type)


def get_dataset_types() -> List[str]:
    """
    Get a list of recombinant dataset types
    """
    return sorted(_get_plugin()._genos)


def get_resource_names() -> List[str]:
    """
    Get a list of recombinant resource names
    """
    return [chromo['resource_name']
            for t in get_dataset_types()
            for chromo in get_geno(t)['resources']]


def get_published_resource_resource_name(res_id: str) -> str:
    try:
        return _get_plugin()._published_resource_ids[res_id]
    except KeyError:
        raise RecombinantException('resource id not found')


def get_dataset_type_for_resource_name(resource_name: str) -> Optional[str]:
    """
    Get the dataset type that contains resource_name,
    or None if not found
    """
    for t in get_dataset_types():
        for resource in get_geno(t)['resources']:
            if resource['resource_name'] == resource_name:
                return t


def get_target_datasets() -> List[str]:
    """
    Find the RecombinantPlugin instance and get its
    configured target datasets (e.g., ['ati', 'pd', ...])
    """
    genos = _get_plugin()._genos
    return sorted((t['target_dataset'] for t in genos.values()))
