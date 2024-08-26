from ckan.plugins.toolkit import _

class RecombinantException(Exception):
    pass

class RecombinantConfigurationError(Exception):
    pass

class BadExcelData(Exception):
    def __init__(self, message):
        self.message = message


def format_trigger_error(error_values: list):
    """
    Format PSQL function errors from raised ValidationError exceptions.

    This method will split the error messages on a unicode private code point (\\uF8FF)
    in order to do string replacements, allowing i18n support in the framework.
    """
    for e in error_values:
        if '\uF8FF' in e:
            yield _(e.split('\uF8FF')[0]).format(e.split('\uF8FF')[1])
        # NOTE: unicode-escape to handle any raw strings from the triggers.
        elif '\uF8FF' in e.encode().decode('unicode-escape'):
            err = e.encode().decode('unicode-escape')
            yield _(err.split('\uF8FF')[0]).format(err.split('\uF8FF')[1])
        else:
            yield _(e)
