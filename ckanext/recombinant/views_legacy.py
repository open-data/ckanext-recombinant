"""
NOTE: this script specifically handles legacy blueprint routes
      which have since had their route paths changed. The blueprint
      functions in this script should only handle redirects.

      we redirect the excel and json schemas/data dictionaries as
      those are most likely to be linked to directly.
"""
from flask import Blueprint, redirect

from typing import cast
from ckan.types import Response

from ckan.plugins.toolkit import h, _
from ckan.views import nocache_store

recombinant_legacy = Blueprint('recombinant_legacy', __name__)


@recombinant_legacy.route('/recombinant-dictionary/<org_name>_<dataset_type>')
@nocache_store
def legacy_org_based_data_dictionary(
        org_name: str, dataset_type: str) -> Response:
    """
    Now: /recombinant/dictionary/<org_name>_<dataset_type>

    See: ckanext.recombinant.views.org_based_data_dictionary
    """
    return cast(Response, redirect(
        h.url_for('recombinant.org_based_data_dictionary',
                  org_name=org_name,
                  dataset_type=dataset_type,
                  qualified=True), code=301))


@recombinant_legacy.route('/recombinant-dictionary/<dataset_type>')
@nocache_store
def legacy_data_dictionary(dataset_type: str) -> Response:
    """
    Now: /recombinant/dictionary/<dataset_type>

    See: ckanext.recombinant.views.data_dictionary
    """
    return cast(Response, redirect(
        h.url_for('recombinant.data_dictionary',
                  dataset_type=dataset_type,
                  qualified=True), code=301))


@recombinant_legacy.route('/recombinant-published-dictionary/<dataset_type>')
@nocache_store
def legacy_published_data_dictionary(dataset_type: str) -> Response:
    """
    Now: /recombinant/published-dictionary/<dataset_type>

    See: ckanext.recombinant.views.published_data_dictionary
    """
    return cast(Response, redirect(
        h.url_for('recombinant.published_data_dictionary',
                  dataset_type=dataset_type,
                  qualified=True), code=301))


@recombinant_legacy.route('/recombinant-schema/<org_name>_<dataset_type>.json')
@nocache_store
def legacy_org_based_schema_json(org_name: str, dataset_type: str) -> Response:
    """
    Now: /recombinant/schema/<org_name>_<dataset_type>.json

    See: ckanext.recombinant.views.org_based_schema_json
    """
    return cast(Response, redirect(
        h.url_for('recombinant.org_based_schema_json',
                  org_name=org_name,
                  dataset_type=dataset_type,
                  qualified=True), code=301))


@recombinant_legacy.route('/recombinant-schema/<dataset_type>.json')
@nocache_store
def legacy_schema_json(dataset_type: str) -> Response:
    """
    Now: /recombinant/schema/<dataset_type>.json

    See: ckanext.recombinant.views.schema_json
    """
    return cast(Response, redirect(
        h.url_for('recombinant.schema_json',
                  dataset_type=dataset_type,
                  qualified=True), code=301))


@recombinant_legacy.route('/recombinant-published-schema/<dataset_type>.json')
@nocache_store
def legacy_published_schema_json(dataset_type: str) -> Response:
    """
    Now: /recombinant/published-schema/<dataset_type>.json

    See: ckanext.recombinant.views.published_schema_json
    """
    return cast(Response, redirect(
        h.url_for('recombinant.published_schema_json',
                  dataset_type=dataset_type,
                  qualified=True), code=301))
