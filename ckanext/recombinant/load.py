import json
import yaml

from typing import Union, Dict, Any, TextIO


def load(f: Union[str, bytes, bytearray, TextIO]) -> Dict[str, Any]:
    if is_yaml(getattr(f, 'name', '')):
        # type_ignore_reason: incomplete typing
        return yaml.safe_load(f)  # type: ignore
    # type_ignore_reason: incomplete typing
    return json.load(f)  # type: ignore


def loads(s: Union[str, bytes, bytearray, TextIO], url: str) -> Dict[str, Any]:
    if is_yaml(url):
        # type_ignore_reason: incomplete typing
        return yaml.safe_load(s)  # type: ignore
    # type_ignore_reason: incomplete typing
    return json.loads(s)  # type: ignore


def is_yaml(n: str) -> bool:
    return n.endswith(('.yaml', '.yml'))
