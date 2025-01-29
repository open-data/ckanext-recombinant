import re
import json
import string
from markupsafe import Markup

from ckanapi import LocalCKAN
from ckan.plugins.toolkit import h, _


FK_DETAILS_MATCH__KEYS = re.compile('(?<=DETAIL:).*(\((.*)\))=')
FK_DETAILS_MATCH__VALUES = re.compile('(?<=DETAIL:).*(\((.*)\))')
FK_DETAILS_MATCH__TABLE = re.compile('(?<=DETAIL:).*"(.*?)"')


class PartialFormat(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def get_constraint_error_from_psql_error(
        lc: LocalCKAN, sql_error_string: str,
        error_message: str) -> Markup:
    """
    Parses the pSQL original constraint error string to determine
    the referenced/referencing keys, values, and table. Formatting
    the passed error message with the values.

    Returns the formatted error message as markupsafe.

    If the resource is a PD type, it will append the key/value filters
    to the reference table URI for a DataTables query.
    """
    keys_match = re.search(FK_DETAILS_MATCH__KEYS, sql_error_string)
    values_match = re.search(FK_DETAILS_MATCH__VALUES, sql_error_string)
    table_match = re.search(FK_DETAILS_MATCH__TABLE, sql_error_string)
    ref_keys = keys_match.group(2) if keys_match else None
    ref_values = values_match.group(2) if values_match else None
    ref_resource = table_match.group(1) if table_match else None
    if ref_resource:
        try:
            ref_res_dict = lc.action.resource_show(id=ref_resource)
            ref_pkg_dict = lc.action.package_show(id=ref_res_dict['package_id'])
            if ref_pkg_dict['type'] in h.recombinant_get_types():
                if ref_keys and ref_values:
                    dt_query = {}
                    _ref_keys = ref_keys.replace(' ', '').split(',')
                    _ref_values = ref_values.replace(' ', '').split(',')
                    for _i, key in enumerate(_ref_keys):
                        dt_query[key] = _ref_values[_i]
                    dt_query = json.dumps(dt_query, separators=(',', ':'))
                ref_res_uri = h.url_for(
                    'recombinant.preview_table',
                    resource_name=ref_res_dict['name'],
                    owner_org=ref_pkg_dict['organization']['name'],
                    dt_query=dt_query)
            else:
                ref_res_uri = h.url_for(
                    'resource.read',
                    id=ref_res_dict['package_id'],
                    resource_id=ref_res_dict['id'])
            ref_resource = ref_res_uri
        except Exception:
            pass
    error_message = _(error_message)  # gettext before formatting
    formatter = string.Formatter()
    mapping = PartialFormat(refKeys=ref_keys,
                            refValues=ref_values,
                            refTable=ref_resource)
    return Markup(formatter.vformat(error_message, (), mapping))
