import pytest

from ckan.tests.factories import Organization, Sysadmin
from ckanext.recombinant.tests import RecombinantTestBase

from ckanapi import LocalCKAN
from ckan.plugins.toolkit import config, ObjectNotFound
from ckanext.recombinant.tables import _get_plugin
from ckanext.recombinant.logic import _action_get_dataset


class TestRecombinantLogic(RecombinantTestBase):
    @classmethod
    def setup_method(self, method):
        """Method is called at class level before EACH test methods of the class are called.
        Setup any state specific to the execution of the given class methods.
        """
        super(TestRecombinantLogic, self).setup_method(method)

        self.sysadmin = Sysadmin()
        self.lc = LocalCKAN()

    def test_deleted_org(self):
        """
        Deleted orgs should not show Recombinant.
        """
        org = Organization()
        _get_plugin().update_config(config)
        self.lc.action.recombinant_create(dataset_type='sample',
                                          owner_org=org['name'])
        _lc, _geno, dataset = _action_get_dataset({'ignore_auth': True,
                                                   'user': self.sysadmin['name']},
                                                  {'dataset_type': 'sample',
                                                   'owner_org': org['name']})
        self.lc.action.package_delete(id=dataset['id'])
        self.lc.action.organization_delete(id=org['id'])
        with pytest.raises(ObjectNotFound):
            self.lc.action.recombinant_show(dataset_type='sample',
                                            owner_org=org['name'])
