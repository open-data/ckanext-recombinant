from __future__ import annotations

from typing import Any, Dict, List, Optional, NamedTuple
from ckan.types import (
    PackageShowDict,
    OrganizationShowDict
)

from typing_extensions import TypedDict, Required, Union


class RecombinantResourceDict(TypedDict, total=False):
    '''
    Dictionary for the Resources compiled in the recombinant_show action.
    '''
    id: Required[Optional[str]]
    name: Required[str]
    description: Required[str]
    metadata_correct: Required[bool]
    shortname: Required[str]
    datastore_correct: bool
    schema_correct: bool
    datastore_rows: int
    datastore_active: bool
    error: str
    datastore_record_state_stats: Dict[str, int]


class RecombinantDict(TypedDict, total=False):
    '''
    Dictionary returned from the recombinant_show action.
    '''
    dataset_type: Required[str]
    owner_org: Required[str]
    org_title: Required[str]
    id: Required[str]
    metadata_correct: Required[bool]
    all_correct: Required[bool]
    resources: Required[List[RecombinantResourceDict]]
    template_updated: Required[Optional[str]]


class RecombinantChoice(TypedDict):
    '''
    Dictionary of choice fields compiled from views._get_choice_fields
    '''
    value: str
    label: str


RecombinantChoiceFieldsDict = Dict[str, List[RecombinantChoice]]


class RecombinantFieldDict(TypedDict, total=False):
    '''
    Dictionary for Resource Fields loaded from Recombinant YAML Schemas.
    '''
    datastore_id: Required[str]
    label: Required[Union[str, Dict[str, str]]]
    description: Required[Union[str, Dict[str, str]]]
    obligation: Union[str, Dict[str, str]]
    format_type: Union[str, Dict[str, str]]
    validation: Union[str, Dict[str, str]]
    occurrence: Union[str, Dict[str, str]]
    datastore_type: Required[str]
    max_chars: int
    excel_required: bool
    excel_column_width: int
    excel_required_formula: str
    excel_error_formula: str
    excel_full_text_choices: bool
    form_required: bool
    datatables_col_class: str
    js_required_eval: str
    js_error_eval: str
    datatables_full_text_choices: bool
    form_attrs: Dict[str, Any]
    form_snippet: str
    preview_class: str
    visible_to_public: bool
    published_resource_computed_field: bool
    import_template_include: bool
    choices: Dict[str, Any]
    choices_fiscal_year: Dict[str, int]
    choices_filter_query: str
    choices_file: str
    choices_reference_table: str
    choices_suffix_filter: Dict[str, Any]
    choices_lookup: Dict[str, Any]
    excel_error_cell_filter_formula: str


class RecombinantChromoDict(TypedDict, total=False):
    '''
    Dictionary for Resource Schemas loaded from Recombinant YAML Schemas.
    '''
    title: Required[str]
    resource_name: Required[str]
    dataset_type: Required[str]
    target_dataset: Required[str]
    _url_path: str
    _path: str
    published_resource_id: str
    excel_template: Required[bool]
    create_form: Required[bool]
    edit_form: Required[bool]
    stately_records: Required[bool]
    fields: Required[List[RecombinantFieldDict]]
    datastore_primary_key: Required[List[str]]
    datastore_indexes: Required[Union[str, List[str]]]
    org_specific_fields: List[str]
    datastore_constraint_error_templates: Dict[str, str]
    datastore_constraint_errors: Dict[str, str]
    default_preview_sort: str
    examples: Required[Dict[str, Any]]
    triggers: Required[List[Union[str, Dict[str, str]]]]
    trigger_strings: Dict[str, str]


class RecombinantGenoDict(TypedDict, total=False):
    '''
    Dictionary loaded from Recombinant YAML Schemas.
    '''
    dataset_type: Required[str]
    target_dataset: Required[str]
    title: Required[str]
    shortname: str
    notes: Required[str]
    template_version: int
    portal_type: Required[str]
    collection: Required[str]
    resources: Required[List[RecombinantChromoDict]]
    excel_edge_style: Dict[str, Any]
    excel_header_style: Dict[str, Any]
    excel_column_heading_style: Dict[str, Any]
    datatables_style: Dict[str, Any]
    template_updated: str
    guide_link: str
    datastore_text_types: List[str]


class RecombinantViewContext(NamedTuple):
    '''
    Immutable class for the shared context for Recombinant views.

    Defines context for instantiated Recombinant Datasets.
    '''
    rcomb: RecombinantDict
    geno: RecombinantGenoDict
    chromo: RecombinantChromoDict
    dataset: PackageShowDict
    resource: RecombinantResourceDict
    organization: OrganizationShowDict
    pk_fields: List[str]
    choice_fields: RecombinantChoiceFieldsDict


class RecombinantUninitializedContext(NamedTuple):
    '''
    Immutable class for the shared context for Recombinant views.

    Defines context for uninitialized Recombinant Datasets.
    '''
    geno: RecombinantGenoDict
    chromo: RecombinantChromoDict
    organization: OrganizationShowDict
    pk_fields: List[str]
    choice_fields: RecombinantChoiceFieldsDict
    rcomb: Optional[RecombinantDict] = None
    dataset: Optional[PackageShowDict] = None
    resource: Optional[RecombinantResourceDict] = None
