import json

from pylons import c, config
from pylons.i18n import gettext
import ckanapi
from ckan.lib.helpers import lang

from ckanext.recombinant.tables import get_chromo, get_geno
from ckanext.recombinant.errors import RecombinantException
from ckanext.recombinant import load


# same as scheming_language_text, copied so we don't add the dependency
def recombinant_language_text(text, prefer_lang=None):
    """
    :param text: {lang: text} dict or text string
    :param prefer_lang: choose this language version if available

    Convert "language-text" to users' language by looking up
    language in dict or using gettext if not a dict
    """
    if not text:
        return u''

    if hasattr(text, 'get'):
        try:
            if prefer_lang is None:
                prefer_lang = lang()
        except:
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

        l, v = sorted(text.items())[0]
        return v

    t = gettext(text)
    if isinstance(t, str):
        return t.decode('utf-8')
    return t


def recombinant_get_chromo(resource_name):
    """
    Get the resource definition (chromo) for the given resource name
    """
    try:
        return get_chromo(resource_name)
    except RecombinantException:
        return

def recombinant_get_geno(dataset_type):
    """
    Get the dataset definition (geno) for thr given dataset type
    """
    try:
        return get_geno(dataset_type)
    except RecombinantException:
        return

def recombinant_primary_key_fields(resource_name):
    try:
        chromo = get_chromo(resource_name)
    except RecombinantException:
        return []
    return [
        f for f in chromo['fields']
        if f['datastore_id'] in chromo['datastore_primary_key']
        ]

def recombinant_example(resource_name, doc_type, indent=2, lang='json'):
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
            "%s%s=%s" % (left, k, json.dumps(data[k]))
            for k in sorted(data))

    out = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
    return left[2:] + ('\n' + left[2:]).join(out.split('\n')[1:-1])


def recombinant_choice_fields(resource_name):
    """
    Return a list of fields from the resource definition
    that contain lists of choices, with labels pre-translated
    """
    out = []
    chromo = recombinant_get_chromo(resource_name)
    if not chromo:
        return []

    def choices(f, choices):
        out.append({
            'datastore_id': f['datastore_id'],
            'label': gettext(f['label']).decode('utf-8'),
            'choices': (v, recombinant_language_text(choices[v]))
                for v in sorted(choices))
            })

    for f in chromo['fields']:
        if 'choices' in f:
            choices(f, f['choices'])
        elif 'choices_file' in f and '_path' in chromo:
            choices(f, _read_choices_file(chromo, f))

    return out


def _read_choices_file(chromo, f):
    with open(os.path.join(chromo['_path'], f['choices_file'])) as cf:
        return load.load(cf)


def recombinant_show_package(pkg):
    """
    return recombinant_show results for pkg
    """
    lc = ckanapi.LocalCKAN(username=c.user)
    return lc.action.recombinant_show(
        dataset_type=pkg['type'],
        owner_org=pkg['organization']['name'])
