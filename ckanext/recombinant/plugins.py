from pylons.i18n import _
import ckan.plugins as p
from ckan.lib.plugins import DefaultDatasetForm

from paste.deploy.converters import asbool

import importlib
import os
import json
import uuid

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




class RecombinantPlugin(p.SingletonPlugin, DefaultDatasetForm):
    p.implements(p.IConfigurer)
    p.implements(p.IDatasetForm, inherit=True)
    p.implements(_IRecombinant)
    p.implements(p.IRoutes, inherit=True)

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
        return 'recombinant/read.html'

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
        map.connect('/recombinant/template/{id}', action='template',
            controller='ckanext.recombinant.controller:UploadController')
        return map


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
        return json.load(open(p))
        
def _load_tables_url(url):
    import urllib2
    try:
        res = urllib2.urlopen(url)
        tables = res.read()
    except urllib2.URLError:
        raise RecombinantException("Could not find recombinant.tables json config file: %s" % url )
        
    return json.loads(tables)


