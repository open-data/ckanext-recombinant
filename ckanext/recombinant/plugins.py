import importlib
import os
import uuid

from ckan.plugins.toolkit import _, get_validator
import ckan.plugins as p
from ckan.lib.plugins import DefaultDatasetForm, DefaultTranslation

from ckanext.recombinant import logic, tables, helpers, load, views, auth, cli, validators
from ckanext.recombinant.errors import RecombinantException

from ckanext.datastore.interfaces import IDataDictionaryForm


class RecombinantPlugin(
        p.SingletonPlugin, DefaultDatasetForm, DefaultTranslation):
    p.implements(tables.IRecombinant)
    p.implements(p.IConfigurer)
    p.implements(p.IDatasetForm, inherit=True)
    p.implements(p.IBlueprint)
    p.implements(p.ITemplateHelpers, inherit=True)
    p.implements(p.IActions)
    p.implements(p.ITranslation)
    p.implements(p.IAuthFunctions)
    p.implements(p.IClick)
    p.implements(p.IValidators)
    p.implements(IDataDictionaryForm, inherit=True)

    def update_config(self, config):
        # add our templates
        p.toolkit.add_template_directory(config, 'templates')
        p.toolkit.add_public_directory(config, 'public')

        # read our configuration early
        self._tables_urls = config.get('recombinant.definitions', ""
            ).split()
        if not self._tables_urls:
            raise RecombinantException("Missing configuration option "
                "recombinant.definitions")
        self._chromos, self._genos = (
            _load_table_definitions(self._tables_urls))
        self._published_resource_ids = {}
        for chname, ch in self._chromos.items():
            pubid = ch.get('published_resource_id')
            if pubid:
                self._published_resource_ids[pubid] = chname

    def package_types(self):
        return tables.get_dataset_types()

    def create_package_schema(self):
        schema = super(RecombinantPlugin, self).create_package_schema()
        schema['id'] = [generate_uuid]
        schema['name'] = [value_from_id]
        schema['resources']['url'] = [p.toolkit.get_validator('ignore_missing')]

        return schema

    def get_blueprint(self):
        return [views.recombinant]

    def prepare_dataset_blueprint(self, package_type, bp):
        bp.add_url_rule('/<id>', 'dataset_redirect', views.dataset_redirect)
        bp.add_url_rule('/edit/<id>', 'dataset_edit_redirect', views.dataset_redirect)
        bp.add_url_rule('/<id>/dictionary/<resource_id>', 'resource_data_dict_redirect', views.resource_redirect)
        return bp

    def prepare_resource_blueprint(self, package_type, bp):
        bp.add_url_rule('/<resource_id>/edit', 'resource_edit_redirect', views.resource_redirect)
        bp.add_url_rule('/<resource_id>', 'resource_view_redirect', views.resource_redirect)
        return bp

    def get_helpers(self):
        return {
            'recombinant_language_text': helpers.recombinant_language_text,
            'recombinant_primary_key_fields':
                helpers.recombinant_primary_key_fields,
            'recombinant_get_chromo': helpers.recombinant_get_chromo,
            'recombinant_get_geno': helpers.recombinant_get_geno,
            'recombinant_get_types': helpers.recombinant_get_types,
            'recombinant_example': helpers.recombinant_example,
            'recombinant_choice_fields': helpers.recombinant_choice_fields,
            'recombinant_show_package': helpers.recombinant_show_package,
            'recombinant_get_field': helpers.recombinant_get_field,
            'recombinant_published_resource_chromo':
                helpers.recombinant_published_resource_chromo,
            }

    def get_actions(self):
        return {
            'recombinant_create': logic.recombinant_create,
            'recombinant_update': logic.recombinant_update,
            'recombinant_show': logic.recombinant_show,
            'datastore_info': logic.recombinant_datastore_info,
            }

    # IAuthFunctions

    def get_auth_functions(self):
        return {
            'package_update': auth.package_update,
            'package_create': auth.package_create,
            'datastore_delete': auth.datastore_delete,
        }

    # IClick

    def get_commands(self):
        return [cli.get_commands()]

    # IValidators

    def get_validators(self):
        return {
            'recombinant_foreign_keys': validators.recombinant_foreign_keys,
        }

    # IDataDictionaryForm

    def update_datastore_create_schema(self, schema):
        recombinant_foreign_keys_validator = get_validator('recombinant_foreign_keys')
        schema['foreign_keys'].append(recombinant_foreign_keys_validator)
        return schema


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
    dataset_definitions = {}
    resource_definitions = {}
    published_resource_definitions = {}
    trigger_definitions = {}
    for url in urls:
        is_url = False
        t, p = _load_tables_module_path(url)
        if not t:
            t = _load_tables_url(url)
            is_url = True

        if t['dataset_type'] in dataset_definitions:
            raise RecombinantException('Recombinant dataset_type "%s" is already defined in %s. Cannot be redefined in %s.'
                                       % (t['dataset_type'], dataset_definitions[t['dataset_type']], url))
        genos[t['dataset_type']] = t
        dataset_definitions[t['dataset_type']] = url

        for chromo in t['resources']:
            if chromo['resource_name'] in resource_definitions:
                raise RecombinantException('Recombinant resource_name "%s" is already defined in %s. Cannot be redefined in %s.'
                                           % (chromo['resource_name'], resource_definitions[chromo['resource_name']], url))
            if 'published_resource_id' in chromo and chromo['published_resource_id'] in published_resource_definitions:
                raise RecombinantException('Published Resource ID "%s" is already defined for "%s" in %s. Cannot be redefined in %s.'
                                           % (chromo['published_resource_id'],
                                              published_resource_definitions[chromo['published_resource_id']]['resource_name'],
                                              published_resource_definitions[chromo['published_resource_id']]['url'], url))
            chromo['dataset_type'] = t['dataset_type']
            if 'target_dataset' in t:
                chromo['target_dataset'] = t['target_dataset']
            if is_url:
                chromo['_url_path'] = url.rsplit('/', 1)[0]
            else:  # used for choices_file paths
                chromo['_path'] = os.path.split(p)[0]
            chromos[chromo['resource_name']] = chromo
            resource_definitions[chromo['resource_name']] = url
            if 'published_resource_id' in chromo:
                published_resource_definitions[chromo['published_resource_id']] = {'url': url, 'resource_name': chromo['resource_name']}
            if 'triggers' in chromo:
                for trigger in chromo['triggers']:
                    if isinstance(trigger, dict):
                        for trigger_name in trigger:
                            if trigger_name in trigger_definitions:
                                raise RecombinantException('Recombinant database trigger "%s" is already defined for "%s" in %s. Cannot be redefined in %s.'
                                                           % (trigger_name, trigger_definitions[trigger_name]['resource_name'],
                                                              trigger_definitions[trigger_name]['url'], url))
                            trigger_definitions[trigger_name] = {'url': url, 'resource_name': chromo['resource_name']}

    return chromos, genos


def _load_tables_module_path(url):
    """
    Given a path like "ckanext.spatialx:my_definition.json"
    find the second part relative to the import path of the first

    returns geno, path if found and None, None if not found
    """
    module, file_name = url.split(':', 1)
    try:
        m = importlib.import_module(module)
    except ImportError:
        return None, None
    p = m.__path__[0]
    p = os.path.join(p, file_name)
    if os.path.exists(p):
        return load.load(open(p)), p


def _load_tables_url(url):
    import urllib2
    try:
        res = urllib2.urlopen(url)
        tables = res.read()
    except urllib2.URLError:
        raise RecombinantException("Could not find recombinant.definitions json config file: %s" % url )

    return load.loads(tables, url)
