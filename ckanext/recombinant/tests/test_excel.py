import pytest
import flask
import mock
from io import BytesIO
from ckanapi import LocalCKAN

from ckan.tests.factories import Organization, Sysadmin
from ckanext.recombinant.tests import RecombinantTestBase

from ckan import model
from ckan.plugins.toolkit import config
from ckanext.recombinant.tables import _get_plugin, get_chromo
from ckanext.recombinant.logic import _action_get_dataset
from ckanext.recombinant.write_excel import (
    excel_template,
    append_data
)
from ckanext.recombinant.views import _process_upload_file


@pytest.mark.usefixtures('with_request_context')
class TestRecombinantExcel(RecombinantTestBase):
    @classmethod
    def setup_method(self, method):
        """Method is called at class level before EACH test methods of the class are called.
        Setup any state specific to the execution of the given class methods.
        """
        super(TestRecombinantExcel, self).setup_method(method)

        self.sysadmin = Sysadmin()
        self.org = Organization()
        self.lc = LocalCKAN()

    def test_excel_template(self, app):
        """
        Should be able to write and read and Excel template based
        on the Schema and DataStore records.
        """
        _get_plugin().update_config(config)

        # setup sample
        self.lc.action.recombinant_create(dataset_type='sample',
                                          owner_org=self.org['name'])
        _lc, _geno, dataset = _action_get_dataset({'ignore_auth': True,
                                                   'user': self.sysadmin['name']},
                                                  {'dataset_type': 'sample',
                                                   'owner_org': self.org['name']})
        org = self.lc.action.organization_show(
            id=self.org['id'],
            include_datasets=False)

        expected_records = [
            {'_id': 1, 'reference_number': 'sheet_test_1', 'year': 2026},
            {'_id': 2, 'reference_number': 'sheet_test_2', 'year': 2025},
            {'_id': 3, 'reference_number': 'sheet_test_3', 'year': 2024},
        ]

        # setup sample ds data
        self.lc.action.datastore_upsert(
            resource_id=dataset['resources'][0]['id'],
            force=True,
            method='insert',
            records=expected_records)

        # reference_number is primary key in sample, can update year
        for r in expected_records:
            r['year'] = 2001
        expected_records.append({'_id': 4, 'reference_number': 'sheet_test_new', 'year': 2026})

        # write excel file, should not raise any exceptions
        chromo = get_chromo(dataset['resources'][0]['name'])
        book = excel_template(dataset['type'], org)
        append_data(book, expected_records, chromo)
        blob = BytesIO()
        book.save(blob)

        # read excel file, should not raise any exceptions
        current_user = model.User.get(self.sysadmin['name'])
        with mock.patch('ckan.lib.helpers.current_user', current_user):
            flask.g.user = self.sysadmin['name']
            _process_upload_file(self.lc, dataset, blob, {}, dry_run=False)

        result = self.lc.action.datastore_search(
            resource_id=dataset['resources'][0]['id'])

        assert result['total'] == 4
        assert result['records'] == expected_records
