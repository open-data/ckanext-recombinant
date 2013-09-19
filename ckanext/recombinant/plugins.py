from pylons.i18n import _
import ckan.plugins as p
from ckan.lib.plugins import DefaultDatasetForm

from paste.deploy.converters import asbool

import importlib
import os
import json

class RecombinantException(Exception):
    pass


class IRecombinant(p.Interface):
    pass


class RecombinantPlugin(p.SingletonPlugin, DefaultDatasetForm):
    p.implements(p.IConfigurer)
    p.implements(p.IDatasetForm, inherit=True)
    p.implements(IRecombinant)

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

