import pytest
from urllib.parse import urlparse

from ckan.tests.factories import Organization, SysadminWithToken

from ckanapi import LocalCKAN
from ckan.plugins.toolkit import h, config, ValidationError

from ckanext.recombinant.tests import RecombinantTestBase

from ckanext.recombinant.tables import _get_plugin
from ckanext.recombinant.views import _get_recombinant_view_context_vars
from ckanext.recombinant.errors import RecombinantViewNotFound


class TestRecombinantViews(RecombinantTestBase):
    @classmethod
    def setup_method(self, method):
        """Method is called at class level before EACH test methods of the class are called.
        Setup any state specific to the execution of the given class methods.
        """
        super(TestRecombinantViews, self).setup_method(method)

        sysadmin = SysadminWithToken()
        self.extra_environ_tester = {'Authorization': sysadmin['token']}
        self.lc = LocalCKAN()
        self.org = Organization()

    def test_view_context_vars(self):
        """
        All of the Recombinant views access the function
        _get_recombinant_view_context_vars to get the RecombinantViewContext
        tuple. If any of the function fails, all of the Recombinant views fail.
        """
        _get_plugin().update_config(config)
        try:
            self.lc.action.recombinant_create(dataset_type='sample',
                                              owner_org=self.org['name'])
        except ValidationError:
            pass

        view_context = _get_recombinant_view_context_vars(
            self.lc, 'sample', self.org['name'])
        assert view_context.chromo['resource_name'] == 'sample'
        assert view_context.geno['dataset_type'] == 'sample'
        assert view_context.rcomb['owner_org'] == self.org['name']
        assert len(view_context.rcomb['resources']) == 1
        assert view_context.dataset['id'] == view_context.rcomb['id']
        assert view_context.dataset['type'] == 'sample'
        assert view_context.resource['name'] == 'sample'
        assert view_context.resource['id']
        assert view_context.organization['name'] == self.org['name']
        assert view_context.organization['id'] == self.org['id']
        assert view_context.pk_fields == ['reference_number']
        assert view_context.choice_fields == {}

        with pytest.raises(RecombinantViewNotFound) as e:
            view_context = _get_recombinant_view_context_vars(
                self.lc, 'blurt', self.org['name'])
        assert 'Recombinant type blurt not found' == str(e)

        with pytest.raises(RecombinantViewNotFound) as e:
            view_context = _get_recombinant_view_context_vars(
                self.lc, 'sample', 'blurt')
        assert 'Resource not found' == str(e)

    def get_relative_offset_from_response(self, response):
        assert response.headers
        assert 'Location' in response.headers
        return urlparse(response.headers['Location'])._replace(scheme='', netloc='').geturl(), \
            urlparse(response.headers['Location'])._replace(scheme='', path='').geturl().replace('/', '')

    def test_legacy_redirects(self, app):
        """
        Some views from views_legacy.py should return 302 redirects
        to their new routes in views.py
        """
        _get_plugin().update_config(config)
        try:
            self.lc.action.recombinant_create(dataset_type='sample',
                                              owner_org=self.org['name'])
        except ValidationError:
            pass

        offset = h.url_for('recombinant_legacy.legacy_org_based_data_dictionary',
                           org_name=self.org['name'],
                           dataset_type='sample')
        response = app.get(offset, extra_environ=self.extra_environ_tester,
                           environ_overrides=self.extra_environ_tester,
                           status=302,
                           follow_redirects=False)  # catch redirect
        offset, _host = self.get_relative_offset_from_response(response)
        expected = h.url_for('recombinant.org_based_data_dictionary',
                             org_name=self.org['name'],
                             dataset_type='sample')
        assert offset == expected

        offset = h.url_for('recombinant_legacy.legacy_data_dictionary',
                           dataset_type='sample')
        response = app.get(offset, extra_environ=self.extra_environ_tester,
                           environ_overrides=self.extra_environ_tester,
                           status=302,
                           follow_redirects=False)  # catch redirect
        offset, _host = self.get_relative_offset_from_response(response)
        expected = h.url_for('recombinant.data_dictionary',
                             dataset_type='sample')
        assert offset == expected

        offset = h.url_for('recombinant_legacy.legacy_published_data_dictionary',
                           dataset_type='sample')
        response = app.get(offset, extra_environ=self.extra_environ_tester,
                           environ_overrides=self.extra_environ_tester,
                           status=302,
                           follow_redirects=False)  # catch redirect
        offset, _host = self.get_relative_offset_from_response(response)
        expected = h.url_for('recombinant.published_data_dictionary',
                             dataset_type='sample')
        assert offset == expected

        offset = h.url_for('recombinant_legacy.legacy_org_based_schema_json',
                           org_name=self.org['name'],
                           dataset_type='sample')
        response = app.get(offset, extra_environ=self.extra_environ_tester,
                           environ_overrides=self.extra_environ_tester,
                           status=302,
                           follow_redirects=False)  # catch redirect
        offset, _host = self.get_relative_offset_from_response(response)
        expected = h.url_for('recombinant.org_based_schema_json',
                             org_name=self.org['name'],
                             dataset_type='sample')
        assert offset == expected

        offset = h.url_for('recombinant_legacy.legacy_schema_json',
                           dataset_type='sample')
        response = app.get(offset, extra_environ=self.extra_environ_tester,
                           environ_overrides=self.extra_environ_tester,
                           status=302,
                           follow_redirects=False)  # catch redirect
        offset, _host = self.get_relative_offset_from_response(response)
        expected = h.url_for('recombinant.schema_json',
                             dataset_type='sample')
        assert offset == expected

        offset = h.url_for('recombinant_legacy.legacy_published_schema_json',
                           dataset_type='sample')
        response = app.get(offset, extra_environ=self.extra_environ_tester,
                           environ_overrides=self.extra_environ_tester,
                           status=302,
                           follow_redirects=False)  # catch redirect
        offset, _host = self.get_relative_offset_from_response(response)
        expected = h.url_for('recombinant.published_schema_json',
                             dataset_type='sample')
        assert offset == expected
