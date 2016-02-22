import importlib
import os
import json
import uuid

from paste.reloader import watch_file
from paste.deploy.converters import asbool
from pylons.i18n import _
import ckan.plugins as p
from ckan.lib.plugins import DefaultDatasetForm

from ckanext.recombinant import logic, tables, helpers

try:
    import yaml
except ImportError:
    yaml = None

class RecombinantException(Exception):
    pass


class RecombinantPlugin(p.SingletonPlugin, DefaultDatasetForm):
    p.implements(tables.IRecombinant)
    p.implements(p.IConfigurer)
    p.implements(p.IDatasetForm, inherit=True)
    p.implements(p.IRoutes, inherit=True)
    p.implements(p.ITemplateHelpers, inherit=True)
    p.implements(p.IActions)

    def update_config(self, config):
        # add our templates
        p.toolkit.add_template_directory(config, 'templates')

        # read our configuration early
        self._tables_urls = config.get('recombinant.definitions', ""
            ).split()
        if not self._tables_urls:
            raise RecombinantException("Missing configuration option "
                "recombinant.definitions")
        self._chromos, self._genos = (
            _load_table_definitions(self._tables_urls))

    def package_types(self):
        return tables.get_dataset_types()

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
        map.connect('/recombinant/preview/{id}/{resource_id}',
            action='preview_table',
            controller='ckanext.recombinant.controller:PreviewController')
        return map

    def get_helpers(self):
        return {
            'recombinant_language_text': helpers.recombinant_language_text,
            'recombinant_primary_key_fields':
                helpers.recombinant_primary_key_fields,
            'recombinant_get_chromo': helpers.recombinant_get_chromo,
            'recombinant_get_geno': helpers.recombinant_get_geno,
            'recombinant_example': helpers.recombinant_example,
            'recombinant_choice_fields': helpers.recombinant_choice_fields,
            'recombinant_show_package': helpers.recombinant_show_package,
            }

    def get_actions(self):
        return {
            'recombinant_create': logic.recombinant_create,
            'recombinant_update': logic.recombinant_update,
            'recombinant_show': logic.recombinant_show,
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


def _load_table_definitions(urls):
    chromos = {}
    genos = {}
    for url in urls:
        t = _load_tables_module_path(url)
        if not t:
            t = _load_tables_url(url)

        genos[t['dataset_type']] = t

        for chromo in t['resources']:
            chromo['dataset_type'] = t['dataset_type']
            chromo['target_dataset'] = t['target_dataset']
            chromos[chromo['resource_name']] = chromo

    return chromos, genos


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
        watch_file(p)
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
    # import pyyaml only if necessary
    return n.endswith(('.yaml', '.yml'))
