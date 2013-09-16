ckanext-recombinant
===================

*This document describes a planned CKAN extension.
The code here doesn't actually accomplish any of this yet.*

This extension creates datasets and datastore tables for all
organizations in a ckan instance and allows combining the
data from all tables into a single CSV for exporting.

This lets us use CKAN's authentication to restrict users to
update only their organizations' tables but have all values
available as a single dataset for our public site.

Add this plugin to your CKAN configuration and link to the
table description file:

```ini
ckan.plugins = datastore recombinant

recombinant.tables = file:///.../mytables.json

#   module-path:file name may also be used, e.g:
#
# recombinant.tables = ckanext.atisummaries:recombinant_tables.json
#
#   will try to load "recombinant_tables.json" from the directory
#   containing the ckanext.atisummaries module
```


Example Table Description File
------------------------------

```json
[
  {
    "dataset_type": "com.example.atisummaries",
    "name": "ati-summaries",
    "title": "ATI Summaries",
    "datastore_table": {
      "fields": [
        {
          "id": "request_number",
          "type": "text",
        },
        {
          "id": "pages",
          "type": "int",
        }
      ],
      "primary_key": "request_number",
      "indexes": "request_number",
    }
  }
]
```

