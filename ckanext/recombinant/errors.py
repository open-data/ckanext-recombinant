from typing import Any, Generator

from ckan.plugins.toolkit import _


class RecombinantException(Exception):
    pass


class RecombinantFieldError(Exception):
    pass


class RecombinantConfigurationError(Exception):
    pass


class BadExcelData(Exception):
    def __init__(self, message: Any):
        self.message = message


def format_trigger_error(error_values: Any) -> Generator[str, None, None]:
    """
    Format PSQL function errors from raised ValidationError exceptions.

    This method will split the error messages on a
    unicode private code point (\\uF8FF) in order to do string
    replacements, allowing i18n support in the framework.
    """
    if not isinstance(error_values, list):
        raise ValueError(f'bad error_values type: {type(error_values)}')

    for e in error_values:
        err, *args = str(e).split('\uF8FF')
        yield _(err).format(*args)
