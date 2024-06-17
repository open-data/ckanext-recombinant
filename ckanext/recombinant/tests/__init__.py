from ckan.tests.helpers import reset_db
from ckan.lib.search import clear_all

class RecombinantTestBase(object):
    @classmethod
    def setup_method(self, method):
        """Method is called at class level before EACH test methods of the class are called.
        Setup any state specific to the execution of the given class methods.
        """
        reset_db()
        clear_all()
