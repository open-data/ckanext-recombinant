import json

try:
    import yaml
except ImportError:
    yaml = None


def load(f):
    if is_yaml(f.name):
        return yaml.safe_load(f)
    return json.load(f)


def loads(s, url):
    if is_yaml(url):
        return yaml.safe_load(s)
    return json.loads(s)


def is_yaml(n):
    # import pyyaml only if necessary
    return n.endswith(('.yaml', '.yml'))
