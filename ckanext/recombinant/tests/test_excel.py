from ckanapi import LocalCKAN

from ckan.tests.factories import Organization, Sysadmin
from ckanext.recombinant.tests import RecombinantTestBase

from ckan.plugins.toolkit import config
from ckanext.recombinant.tables import _get_plugin, get_chromo, get_geno
from ckanext.recombinant.logic import _action_get_dataset
from ckanext.recombinant.read_excel import read_excel, get_records
from ckanext.recombinant.write_excel import (
    excel_template,
    append_data
)
from ckanext.recombinant.helpers import recombinant_get_types


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

    def test_excel_template(self):
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
            {'reference_number': 'sheet_test_1', 'year': 2026},
            {'reference_number': 'sheet_test_2', 'year': 2025},
            {'reference_number': 'sheet_test_3', 'year': 2024},
        ]

        # setup sample ds data
        self.lc.action.datastore_upsert(
            resource_id=dataset['resources'][0]['id'],
            force=True,
            method='insert',
            records=expected_records)
        result = self.lc.action.datastore_search(resource_id=['resources'][0]['id'])
        record_data = result['records']

        # write excel file
        chromo = get_chromo(dataset['resources'][0]['id'])
        book = excel_template(dataset['type'], org)
        append_data(book, record_data, chromo)

        # read excel file
        expected_sheet_names = dict(
            (resource['name'], resource['id'])
            for resource in dataset['resources'])
        bad_types = recombinant_get_types()
        bad_types.remove(dataset['type'])
        bad_sheet_names = []
        for bt in bad_types:
            brs = get_geno(bt).get('resources', [])
            bad_sheet_names += [br['resource_name'] for br in brs]
        upload_data = read_excel(book, expected_sheet_names.keys(), bad_sheet_names)
        sheet_name, org_name, column_names, rows = next(upload_data)

        while column_names and column_names[-1] is None:
            column_names.pop()

        records = get_records(rows, [f for f in chromo['fields']],
                              chromo.get('datastore_primary_key', []), {})

        assert sheet_name == dataset['resources'][0]['name']
        assert org_name == org['name']
        assert column_names == ['reference_number', 'year']
        assert len(records) == 3
        assert records == expected_records
