"""
NOTE: this script specifically handles legacy blueprint routes
      which have since had their route paths changed. The blueprint
      functions in this script should only handle redirects.
"""
from flask import Blueprint, redirect

from typing import Union, cast
from ckan.types import Response

from ckanapi import LocalCKAN
from ckan.plugins.toolkit import g, h, _, ObjectNotFound, NotAuthorized, abort

from ckan.views import nocache_store
from ckan.views.dataset import _get_package_type

recombinant_legacy = Blueprint('recombinant_legacy', __name__)


@recombinant_legacy.route('/recombinant/upload/<id>', methods=['GET', 'POST'])
def legacy_upload(id: str) -> Union[Response, str]:
    """
    Now: /recombinant/upload/<resource_name>/<owner_org>

    See: ckanext.recombinant.views.upload
    """
    package_type = _get_package_type(id)
    lc = LocalCKAN(username=g.user)
    try:
        dataset = lc.action.package_show(id=id)
    except (NotAuthorized, ObjectNotFound):
        return abort(404, _('Resource not found'))
    return cast(Response, redirect(
        h.url_for('recombinant.upload',
                  resource_name=package_type,
                  owner_org=dataset['owner_org'],
                  qualified=True), code=301))


@recombinant_legacy.route('/recombinant/delete/<id>/<resource_id>',
                          methods=['GET', 'POST'])
def legacy_delete_records(id: str, resource_id: str) -> Union[str, Response]:
    """
    Now: /recombinant/manage/<resource_name>/<owner_org>/bulk-delete

    See: ckanext.recombinant.views.delete_records
    """
    lc = LocalCKAN(username=g.user)
    try:
        pkg = lc.action.package_show(id=id)
        res = lc.action.resource_show(id=resource_id)
    except (NotAuthorized, ObjectNotFound):
        return abort(404, _('Resource not found'))
    return cast(Response, redirect(
        h.url_for('recombinant.delete_records',
                  resource_name=res['name'],
                  owner_org=pkg['owner_org'],
                  qualified=True), code=301))


@recombinant_legacy.route('/recombinant/delete-selected-records/<resource_id>',
                          methods=['GET', 'POST'])
def legacy_delete_selected_records(resource_id: str):
    """
    Now: /recombinant/manage/<resource_name>/<owner_org>/delete-selected-records

    See: ckanext.recombinant.views.delete_selected_records
    """
    lc = LocalCKAN(username=g.user)
    try:
        res = lc.action.resource_show(id=resource_id)
        pkg = lc.action.package_show(id=res['package_id'])
    except (NotAuthorized, ObjectNotFound):
        return abort(404, _('Resource not found'))
    return cast(Response, redirect(
        h.url_for('recombinant.delete_selected_records',
                  resource_name=res['name'],
                  owner_org=pkg['owner_org'],
                  qualified=True), code=301))


@recombinant_legacy.route('/recombinant/delete_dataset/<id>/<resource_id>',
                          methods=['GET', 'POST'])
def legacy_delete_dataset(id: str, resource_id: str) -> Union[str, Response]:
    """
    Now: /recombinant/manage/<resource_name>/<owner_org>/delete-dataset

    See: ckanext.recombinant.views.delete_dataset
    """
    lc = LocalCKAN(username=g.user)
    try:
        pkg = lc.action.package_show(id=id)
        res = lc.action.resource_show(id=resource_id)
    except (NotAuthorized, ObjectNotFound):
        return abort(404, _('Resource not found'))
    return cast(Response, redirect(
        h.url_for('recombinant.delete_dataset',
                  resource_name=res['name'],
                  owner_org=pkg['owner_org'],
                  qualified=True), code=301))


@recombinant_legacy.route(
        '/recombinant-template/<dataset_type>_<lang>_<owner_org>.xlsx',
        methods=['GET', 'POST'])
def legacy_template(dataset_type: str, lang: str,
                    owner_org: str) -> Union[Response, str]:
    """
    Now: /recombinant/template/<dataset_type>_<lang>_<owner_org>.xlsx

    See: ckanext.recombinant.views.template
    """
    return cast(Response, redirect(
        h.url_for('recombinant.template',
                  dataset_type=dataset_type,
                  lang=lang,
                  owner_org=owner_org,
                  qualified=True), code=301))


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
                  org_name= org_name,
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


@recombinant_legacy.route('/recombinant/refresh/<resource_name>/<owner_org>',
                          methods=['GET', 'POST'])
def legacy_refresh_dataset(resource_name: str, owner_org: str):
    """
    Now: /recombinant/manage/<resource_name>/<owner_org>/refresh

    See: ckanext.recombinant.views.refresh_dataset
    """
    return cast(Response, redirect(
        h.url_for('recombinant.refresh_dataset',
                  resource_name=resource_name,
                  owner_org=owner_org,
                  qualified=True), code=301))


@recombinant_legacy.route('/create-pd-record/<owner_org>/<resource_name>',
                          methods=['GET', 'POST'])
def legacy_create_record(owner_org: str, resource_name: str):
    """
    Now: /recombinant/manage/<resource_name>/<owner_org>/create-record

    See: ckanext.recombinant.views.create_record
    """
    return cast(Response, redirect(
        h.url_for('recombinant.create_record',
                  resource_name=resource_name,
                  owner_org=owner_org,
                  qualified=True), code=301))


@recombinant_legacy.route('/update-pd-record/<owner_org>/<resource_name>/<pk>',
                          methods=['GET', 'POST'])
def legacy_update_record(owner_org: str, resource_name: str, pk: str):
    """
    Now: /recombinant/manage/<resource_name>/<owner_org>/update-record/<pk>

    See: ckanext.recombinant.views.update_record
    """
    return cast(Response, redirect(
        h.url_for('recombinant.update_record',
                  resource_name=resource_name,
                  owner_org=owner_org,
                  qualified=True), code=301))


@recombinant_legacy.route('/upsert_pd_data/<owner_org>/<resource_name>',
                          methods=['POST'])
def legacy_upsert_data(owner_org: str, resource_name: str):
    """
    Now: /recombinant/manage/<resource_name>/<owner_org>/upsert-data

    See: ckanext.recombinant.views.upsert_data
    """
    return cast(Response, redirect(
        h.url_for('recombinant.upsert_data',
                  resource_name=resource_name,
                  owner_org=owner_org,
                  qualified=True), code=301))
