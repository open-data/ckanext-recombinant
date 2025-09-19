import json
import os.path
from markupsafe import Markup

from typing import Dict, Any, Optional, List, Union

from ckan.plugins.toolkit import c, config
from ckan.plugins.toolkit import _ as gettext
import ckanapi
from ckan.lib.helpers import lang

from ckanext.recombinant.tables import (
    get_chromo, get_geno, get_dataset_types,
    get_published_resource_resource_name
)
from ckanext.recombinant.errors import RecombinantException
from ckanext.recombinant import load


# same as scheming_language_text, copied so we don't add the dependency
def recombinant_language_text(text: Any,
                              prefer_lang: Optional[str] = None) -> str:
    """
    :param text: {lang: text} dict or text string
    :param prefer_lang: choose this language version if available

    Convert "language-text" to users' language by looking up
    language in dict or using gettext if not a dict
    """
    if not text:
        return ''

    if hasattr(text, 'get'):
        try:
            if prefer_lang is None:
                prefer_lang = lang()
        except Exception:
            pass  # lang() call will fail when no user language available
        else:
            try:
                return text[prefer_lang]
            except KeyError:
                pass

        default_locale = config.get('ckan.locale_default', 'en')
        try:
            return text[default_locale]
        except KeyError:
            pass

        _l, v = sorted(text.items())[0]
        return v

    t = gettext(text)
    return t


def recombinant_get_chromo(resource_name: str) -> Optional[Dict[str, Any]]:
    """
    Get the resource definition (chromo) for the given resource name
    """
    try:
        return get_chromo(resource_name)
    except RecombinantException:
        return


def recombinant_get_geno(dataset_type: str) -> Optional[Dict[str, Any]]:
    """
    Get the dataset definition (geno) for thr given dataset type
    """
    try:
        return get_geno(dataset_type)
    except RecombinantException:
        return


def recombinant_get_types() -> List[str]:
    return get_dataset_types()


def recombinant_primary_key_fields(resource_name: str) -> List[Dict[str, Any]]:
    try:
        chromo = get_chromo(resource_name)
    except RecombinantException:
        return []
    return [
        f for f in chromo['fields']
        if f['datastore_id'] in chromo['datastore_primary_key']
        ]


def recombinant_example(resource_name: str,
                        doc_type: str,
                        indent: int = 2,
                        lang: str = 'json') -> str:
    """
    Return example data formatted for use in API documentation
    """
    chromo = recombinant_get_chromo(resource_name)
    if chromo and doc_type in chromo.get('examples', {}):
        data = chromo['examples'][doc_type]
    elif doc_type == 'sort':
        data = "request_date desc, file_number asc"
    elif doc_type == 'filters':
        data = {"resource": "doc", "priority": "high"}
    elif doc_type == 'filter_one':
        data = {"file_number": "86086"}
    else:
        data = {
            "request_date": "2016-01-01",
            "file_number": "42042",
            "resource": "doc",
            "prioroty": "low",
        }

    if not isinstance(data, (list, dict)):
        return json.dumps(data)

    left = ' ' * indent

    if lang == 'pythonargs':
        return ',\n'.join(
            # type_ignore_reason: incomplete typing
            "%s%s=%s" % (left, k, json.dumps(data[k]))  # type: ignore
            for k in sorted(data))

    out = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
    return left[2:] + ('\n' + left[2:]).join(out.split('\n')[1:-1])


def _filter_choices_for_org(choices: Dict[str, Any],
                            org_name: str):
    invalid_choices = []
    for choice_key, choice_obj in choices.items():
        if 'valid_orgs' not in choice_obj:
            continue
        _valid_orgs = choice_obj['valid_orgs']
        if isinstance(_valid_orgs, dict):
            _valid_orgs = _valid_orgs.keys()
        if org_name in _valid_orgs:
            continue
        invalid_choices.append(choice_key)
    for key in invalid_choices:
        del choices[key]


def recombinant_org_specific_fields(resource_name: str) -> Dict[str, Any]:
    chromo = recombinant_get_chromo(resource_name)
    if not chromo:
        return {}
    return set(
        x for trigger in chromo.get('per_org_triggers', {}).values() for x in trigger)


def recombinant_choice_fields(resource_name: str,
                              all_languages: bool = False,
                              prefer_lang: Optional[str] = None,
                              org_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Return a datastore_id: choices dict from the resource definition
    that contain lists of choices, with labels pre-translated
    and sorted by key (or custom choice_order_expression)

    all_languages - set to True to return all label languages
    prefer_lang - set all_languages to False and use prefer_lang
        to request translations for a specific language
    """
    out = {}
    chromo = recombinant_get_chromo(resource_name)
    if not chromo:
        return {}

    org_specific_fields = set(
        x for trigger in chromo.get('per_org_triggers', {}).values() for x in trigger)

    def build_choices(f: Dict[str, Any], choices: Dict[str, Any]):
        order_expr = f.get('choice_order_expression')
        if order_expr:
            code = compile(order_expr, resource_name, 'eval')

            def key_fn(v: str) -> Any:
                return eval(code, {}, {
                    'code': v,
                    'value': choices[v],
                    'text': recombinant_language_text(choices[v], prefer_lang),
                })
        else:
            key_fn = None  # type: ignore

        exclude_choices = f.get('exclude_choices', [])
        if f['datastore_id'] in org_specific_fields:
            _filter_choices_for_org(choices, org_name)
        out[f['datastore_id']] = [
            (v, choices[v] if all_languages
                else recombinant_language_text(choices[v], prefer_lang))
            for v in sorted(choices, key=key_fn)
            if v not in exclude_choices
        ]

    for f in chromo['fields']:
        if 'choices' in f:
            build_choices(f, f['choices'])
        elif 'choices_file' in f and '_path' in chromo:
            build_choices(f, _read_choices_file(chromo, f))

    return out


def _read_choices_file(chromo: Dict[str, Any], f: Dict[str, Any]) -> Dict[str, Any]:
    with open(os.path.join(chromo['_path'], f['choices_file'])) as cf:
        return load.load(cf)


def recombinant_show_package(pkg: Dict[str, Any]) -> Dict[str, Any]:
    """
    return recombinant_show results for pkg
    """
    lc = ckanapi.LocalCKAN(username=c.user)
    return lc.action.recombinant_show(
        dataset_type=pkg['type'],
        owner_org=pkg['organization']['name'])


def recombinant_get_field(resource_name: str,
                          datastore_id: str) -> Optional[Dict[str, Any]]:
    """
    Return field info from resource name and datastore column id
    """
    chromo = recombinant_get_chromo(resource_name)
    if not chromo:
        return
    for f in chromo['fields']:
        if f['datastore_id'] == datastore_id:
            return f


def recombinant_published_resource_chromo(res_id: str) -> Optional[Dict[str, Any]]:
    try:
        resource_name = get_published_resource_resource_name(res_id)
        return recombinant_get_chromo(resource_name)
    except RecombinantException:
        return {}


def obfuscate_to_code_points(string: str,
                             return_safe: bool = True) -> Union[Markup, str]:
    """
    Obfuscate each string character to its code point.
    """
    obfuscated_string = ''
    for _s in string:
        obfuscated_string += f'&#{ord(_s):03d};'
    return Markup(obfuscated_string) if return_safe \
        else obfuscated_string


def support_email_address(xml_encode: bool = True) -> Union[Markup, str]:
    return config.get('ckanext.canada.support_email_address', '') if not xml_encode \
        else obfuscate_to_code_points(
            config.get('ckanext.canada.support_email_address', ''))
