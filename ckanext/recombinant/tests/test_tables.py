import os
import pytest

from ckan.tests.helpers import change_config
from ckan.plugins.toolkit import config

from ckanext.recombinant.tests import RecombinantTestBase
from ckanext.recombinant.tables import (
    get_dataset_types,
    get_geno,
    get_chromo,
    get_resource_names,
    get_published_resource_resource_name,
    get_dataset_type_for_resource_name,
    get_target_datasets,
    _get_plugin
)
from ckanext.recombinant.errors import RecombinantException


class TestRecombinantTables(RecombinantTestBase):

    expected_chromo = {
        'title': 'Sample Resource',
        'resource_name': 'sample',
        'published_resource_id': '1495491e-338c-43ec-9995-ecb48c67d17e',
        'create_form': True,
        'edit_form': True,
        'fields': [
            {
                'datastore_id': 'reference_number',
                'label': {'en': 'Reference Number', 'fr': 'Reference Number FR'},
                'description': {'en': 'Sample Reference Number Field', 'fr': 'Sample Reference Number Field FR'},
                'obligation': 'Mandatory',
                'excel_required': True,
                'form_required': True,
                'format_type': 'Free text',
                'validation': 'This field must not be empty',
                'visible_to_public': True,
                'occurrence': 'Single',
                'datastore_type': 'text'
            },
            {
                'datastore_id': 'year',
                'datastore_type': 'year',
                'label': 'Year',
                'description': {'en': 'Sample Year Field', 'fr': 'SampleYear Field FR'},
                'obligation': 'Mandatory',
                'excel_required': True,
                'form_required': True,
                'validation': 'This field must not be empty',
                'excel_column_width': 10,
                'extract_date_year': True,
                'form_attrs': {'size': 20}
            }
        ],
        'datastore_primary_key': 'reference_number',
        'datastore_indexes': '',
        'default_preview_sort': 'reference_number',
        'excel_example_height': 100,
        'excel_data_num_rows': 500,
        'triggers': [{
            'test_trigger_1': "DECLARE\n  errors text[][] := '{{}}';\n  crval RECORD;\nBEGIN\n  errors := errors || required_error(NEW.reference_number, 'reference_number');\n  errors := errors || required_error(NEW.year, 'year');\n\n  IF errors = '{{}}' THEN\n    RETURN NEW;\n  END IF;\n  RAISE EXCEPTION E'TAB-DELIMITED\\t%', array_to_string(errors, E'\\t');\nEND;\n"
        }],
        'examples': {
            'record': {'reference_number': 'T-2019-Q3-00001', 'year': 2024},
            'filter_one': {'reference_number': 'T-2019-Q3-00001'},
            'sort': 'year desc'
        },
        'dataset_type': 'sample',
        'target_dataset': 'sample',
        '_path': os.path.dirname(os.path.realpath(__file__)) + '/samples'
    }
    expected_geno = {
        'dataset_type': 'sample',
        'target_dataset': 'sample',
        'title': 'Sample Dataset Type',
        'shortname': 'Sample Dataset Type',
        'notes': 'Sample Dataset Type',
        'template_version': 3,
        'portal_type': 'dataset',
        'collection': 'sample',
        'resources': [expected_chromo],
        'excel_edge_style': {'PatternFill': {'fgColor': 'FF336B87', 'patternType': 'solid'}},
        'excel_header_style': {'PatternFill': {'patternType': 'solid', 'fgColor': 'FF6832e3'}},
        'excel_column_heading_style': {'PatternFill': {'patternType': 'solid', 'fgColor': 'FFEFEFEF'}}
    }

    @classmethod
    def setup_method(self, method):
        """Method is called at class level before EACH test methods of the class are called.
        Setup any state specific to the execution of the given class methods.
        """
        super(TestRecombinantTables, self).setup_method(method)

    def test_get_dataset_types(self):
        """Should return a list of loaded dataset types from Recombinant"""
        _get_plugin().update_config(config)
        dtypes = get_dataset_types()
        assert dtypes == ['sample']

    def test_get_geno(self):
        """Should return a dictionary from the loaded yaml."""
        _get_plugin().update_config(config)
        geno = get_geno(get_dataset_types()[0])
        assert geno == self.expected_geno

    def test_get_chromo(self):
        """Should return a dictionary from the loaded yaml for a specific Recombinant resource name."""
        _get_plugin().update_config(config)
        chromo = get_chromo('sample')
        assert chromo == self.expected_chromo

    def test_get_resource_names(self):
        """Should return a list of all Recombinant resource names."""
        _get_plugin().update_config(config)
        resource_names = get_resource_names()
        assert resource_names == ['sample']

    def test_get_published_resource_resource_name(self):
        """Should return the Recombinant resource name from a published resourd ID."""
        _get_plugin().update_config(config)
        resource_name = get_published_resource_resource_name('1495491e-338c-43ec-9995-ecb48c67d17e')
        assert resource_name == 'sample'

    def test_get_dataset_type_for_resource_name(self):
        """Should return the dataset type from the given Recombinant resource name."""
        _get_plugin().update_config(config)
        dtype = get_dataset_type_for_resource_name('sample')
        assert dtype == 'sample'

    def test_get_target_datasets(self):
        """Should return a list of all target dataset types from Recombinant."""
        _get_plugin().update_config(config)
        target_dtypes = get_target_datasets()
        assert target_dtypes == ['sample']

    @change_config('recombinant.definitions', 'ckanext.recombinant.tests:samples/sample.yaml ckanext.recombinant.tests:samples/sample_dupe_dtype.yaml')
    def test_load_table_definitions_duplicate_dataset_type(self):
        """Should fail if there is a duplicate dataset_type across table definitions."""
        with pytest.raises(RecombinantException) as re:
            _get_plugin().update_config(config)
        assert 'Recombinant dataset_type' in str(re)
        assert 'already defined in ckanext.recombinant.tests:samples/sample.yaml' in str(re)

    @change_config('recombinant.definitions', 'ckanext.recombinant.tests:samples/sample.yaml ckanext.recombinant.tests:samples/sample_dupe_rname.yaml')
    def test_load_table_definitions_duplicate_resource_names(self):
        """Should fail if there is a duplicate resource_name across table definitions."""
        with pytest.raises(RecombinantException) as re:
            _get_plugin().update_config(config)
        assert 'Recombinant resource_name' in str(re)
        assert 'already defined in ckanext.recombinant.tests:samples/sample.yaml' in str(re)

    @change_config('recombinant.definitions', 'ckanext.recombinant.tests:samples/sample.yaml ckanext.recombinant.tests:samples/sample_dupe_published_rid.yaml')
    def test_load_table_definitions_duplicate_published_resource_ids(self):
        """Should fail if there is a duplicate published_resource_id across table definitions."""
        with pytest.raises(RecombinantException) as re:
            _get_plugin().update_config(config)
        assert 'Published Resource ID' in str(re)
        assert 'already defined for "sample" in ckanext.recombinant.tests:samples/sample.yaml' in str(re)

    @change_config('recombinant.definitions', 'ckanext.recombinant.tests:samples/sample.yaml ckanext.recombinant.tests:samples/sample_dupe_trigger_name.yaml')
    def test_load_table_definitions_duplicate_database_trigger_names(self):
        """Should fail if there is a duplicate triggers dictionary key across table definitions."""
        with pytest.raises(RecombinantException) as re:
            _get_plugin().update_config(config)
        assert 'Recombinant database trigger' in str(re)
        assert 'already defined for "sample" in ckanext.recombinant.tests:samples/sample.yaml' in str(re)
