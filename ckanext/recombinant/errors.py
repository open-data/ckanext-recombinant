from typing import List, Any, Generator

from ckan.plugins.toolkit import _


class RecombinantException(Exception):
    pass


class RecombinantConfigurationError(Exception):
    pass


class BadExcelData(Exception):
    def __init__(self, message: Any):
        self.message = message


def format_trigger_error(error_values: List[str]) -> Generator[str, None, None]:
    """
    Format PSQL function errors from raised ValidationError exceptions.

    This method will split the error messages on a
    unicode private code point (\\uF8FF) in order to do string
    replacements, allowing i18n support in the framework.
    """
    for e in error_values:
        if '\uF8FF' in e:
            yield _(e.split('\uF8FF')[0]).format(e.split('\uF8FF')[1])
        else:
            yield _(e)
