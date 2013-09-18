from pylons.i18n import _
import ckan.plugins as p
from ckan.lib.plugins import DefaultDatasetForm

from paste.deploy.converters import asbool

import importlib
import os
import json

class RecombinantException(Exception):
    pass


class RecombinantPlugin(p.SingletonPlugin, DefaultDatasetForm):
    p.implements(p.IConfigurer)
    p.implements(p.IConfigurable)
    p.implements(p.ITemplateHelpers)
    p.implements(p.IDatasetForm, inherit=True)

    _schemas = None

    def update_config(self, config):
        # add our templates
        p.toolkit.add_template_directory(config, 'templates')

    def update_config(self, config):
        self._tables_url = config.get('recombinant.tables', ""
            ).strip()
        if not self._tables_url:
            raise RecombinantException("Missing configuration option "
                "recombinant.tables")
        assert 0, _load_tables(self._tables_url)

    def package_types(self):
        assert 0, 'shouldnt be called yet'



def _load_tables(url):
    tables = _load_tables_module_path(url)
    if not tables:
        tables = _load_tables_url(url)
    return json.load(tables)


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
        return open(p)

