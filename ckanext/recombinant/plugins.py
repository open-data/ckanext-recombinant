from pylons.i18n import _
import ckan.plugins as p
from ckan.lib.plugins import DefaultDatasetForm

from paste.deploy.converters import asbool

import importlib
import os
import json
import uuid

try:
    import yaml
except ImportError:
    yaml = None

class RecombinantException(Exception):
    pass


class _IRecombinant(p.Interface):
    pass


def _get_tables():
    """
    Find the RecombinantPlugin instance and get the
    table configuration from it
    """
    tables = []
    for plugin in p.PluginImplementations(_IRecombinant):
        tables.extend(plugin._tables)
    return tables


def get_table(dataset_type):
    """
    Get the table configured with the input dataset type
    """
    tables = _get_tables()
    for t in tables:
        if t['dataset_type'] == dataset_type:
            break
    else:
        raise RecombinantException('dataset_type "%s" not found'
            % dataset_type)
    return t


def get_target_datasets():
    """
    Find the RecombinantPlugin instance and get its
    configured target datasets (e.g., ['ati', 'pd', ...])
    """
    tables = _get_tables()
    return list(set((t['target_dataset'] for t in tables)))


def get_dataset_types(target_dataset):
    """
    Find the RecombinantPlugin instance and get its
    configured dataset types for the input target dataset
    """
    tables = _get_tables()
    return (
        t['dataset_type'] for t in tables
            if t['target_dataset'] == target_dataset)


class RecombinantPlugin(p.SingletonPlugin, DefaultDatasetForm):
    p.implements(p.IConfigurer)
    p.implements(p.IDatasetForm, inherit=True)
    p.implements(_IRecombinant)
    p.implements(p.IRoutes, inherit=True)
    p.implements(p.ITemplateHelpers, inherit=True)

    def update_config(self, config):
        # add our templates
        p.toolkit.add_template_directory(config, 'templates')

        # read our configuration early
        self._tables_url = config.get('recombinant.tables', ""
            ).strip()
        if not self._tables_url:
            raise RecombinantException("Missing configuration option "
                "recombinant.tables")
        self._tables = _load_tables(self._tables_url)

    def package_types(self):
        return [t['dataset_type'] for t in self._tables]

    def read_template(self):
        return 'recombinant/edit.html'

    def edit_template(self):
        return 'recombinant/edit.html'

    def create_package_schema(self):
        schema = super(RecombinantPlugin, self).create_package_schema()
        schema['id'] = [generate_uuid]
        schema['name'] = [value_from_id]
        schema['resources']['url'] = [p.toolkit.get_validator('ignore_missing')]

        return schema

    def before_map(self, map):
        map.connect('/recombinant/upload/{id}', action='upload',
            conditions=dict(method=['POST']),
            controller='ckanext.recombinant.controller:UploadController')
        map.connect('/recombinant/delete/{id}', action='delete_record',
            conditions=dict(method=['POST']),
            controller='ckanext.recombinant.controller:UploadController')
        map.connect('/recombinant/template/{id}', action='template',
            controller='ckanext.recombinant.controller:UploadController')
        return map

    def get_helpers(self):
        return {
            'recombinant_primary_key_fields': primary_key_fields,
            'recombinant_get_table': recombinant_get_table,
            }


def generate_uuid(value):
    """
    Create an id for this dataset earlier than normal.
    """
    return str(uuid.uuid4())

def value_from_id(key, converted_data, errors, context):
    """
    Copy the 'id' value from converted_data
    """
    converted_data[key] = converted_data[('id',)]



def _load_tables(url):
    tables = _load_tables_module_path(url)
    if not tables:
        tables = _load_tables_url(url)
    return tables


def _load_tables_module_path(url):
    """
    Given a path like "ckanext.spatialx:recombinant_tables.json"
    find the second part relative to the import path of the first

    returns None if not found
    """
    module, file_name = url.split(':', 1)
    try:
        m = importlib.import_module(module)
    except ImportError:
        return
    p = m.__path__[0]
    p = os.path.join(p, file_name)
    if os.path.exists(p):
        return load(open(p))

def _load_tables_url(url):
    import urllib2
    try:
        res = urllib2.urlopen(url)
        tables = res.read()
    except urllib2.URLError:
        raise RecombinantException("Could not find recombinant.tables json config file: %s" % url )

    return loads(tables, url)


def load(f):
    if is_yaml(f.name):
        return yaml.load(f)
    return json.load(f)

def loads(s, url):
    if is_yaml(url):
        return yaml.load(s)
    return json.loads(s)


def is_yaml(n):
    return n[-5:].lower() == '.yaml' or n[-4:] == '.yml'


def primary_key_fields(dataset_type):
    t = get_table(dataset_type)
    return [
        f for f in t['fields']
        if f['datastore_id'] in t['datastore_primary_key']
        ]

def recombinant_get_table(dataset_type):
    try:
        return get_table(dataset_type)
    except RecombinantError:
        return
