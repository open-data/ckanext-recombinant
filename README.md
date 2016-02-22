ckanext-recombinant
===================

This extension creates datasets and datastore tables for all
organizations in a ckan instance and allows combining the
data from all tables into CSVs for exporting.

This lets us use CKAN's authentication to restrict users to
update only their organizations' tables but have all values
available as a single dataset for our public site.

Recombinant provides template excel files for end users
to bulk import or update data. It also provides a form to
delete individual rows that have been imported.


Datasets and Recombinant Definitions
------------------------------------

![Recombinant Overview](images/recombinant_overview.png)

Recombinant definitions control the behaviour of this extension.
Dataset types are registered using an IDatasetForm plugin and
must be unique across the CKAN instance.

The `paster recombinant create` command will create or update
datasets for every organization to match the definition
for its type, including updating fields, resources and
creating or updating datastore table fields, primary keys and
indexes.

Examples provided will be used to generate API documentation
for end users.


Installation
------------

Add this plugin to your CKAN configuration and link to your
recombinant definition files:

```ini
ckan.plugins = datastore recombinant

recombinant.definitions = file:///.../type1.yaml ...

#   module-path:file name may also be used, e.g:
#
# recombinant.definitions = ckanext.atisummaries:ati.yaml
#
#   will try to load "ati.yaml" from the directory
#   containing the ckanext.atisummaries module
```


Supported Datastore Types
-------------------------

Each "fields" entry in the JSON table description file
describes a field in the dataset. In particular, its
"datastore_type" key codifies its type.

The ckanext-recombinant extension supports the following
data type specifications, with their respective semantics:

```"datastore_type": "text"```
The field is a text value, corresponding to a text column
in the database. It takes no specific input format in
the .xls template. Such fields default to a blank unicode
string.

```"datastore_type": "int"```
The field is a numeric value, corresponding to an integer
column in the database. It takes a .xls template format
using space-separated digit groups; the execution
canonicalizes content to an integer on write. Such
fields default to zero.

```"datastore_type": "year"```
The field is a year value, corresponding to an integer
column in the database. It takes a .xls template format
citing a four digit integer; the execution canonicalizes
content to an integer on write. Such fields default to zero.

```"datastore_type": "month"```
The field is a month value, corresponding to an integer
column in the database. It takes a .xls template format
citing a two digit integer, left-zero-padded; the execution
canonicalizes content to an integer on write. Such fields
default to zero.

```"datastore_type": "date"```
The field is a date value, corresponding to a text
column in the database. It takes a .xls template format
specifying an ISO 8601 date (yyyy-mm-dd). Such fields
default to a blank unicode string.

```"datastore_type": "money"```
The field is a text value, corresponding to a text
column in the database. It takes a xls template template
format specifying a dollar sign ('$') prefix and space-
separated digit groups; the execution reduces content
to an integral numeric string on write. Such fields
default to a blank unicode string.
