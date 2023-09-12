
class RecombinantException(Exception):
    pass

class RecombinantConfigurationError(Exception):
    pass

class BadExcelData(Exception):
    def __init__(self, message):
        self.message = message
