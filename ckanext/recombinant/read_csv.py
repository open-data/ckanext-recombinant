from unicodecsv import DictReader
import codecs

BATCH_SIZE = 20000

def csv_data_batch(csv_path, chromo):
    """
    Generator of dataset records from csv file

    :param csv_path: file to parse
    :param chromo: recombinant resource definition

    :return a batch of records for at most one organization
    :rtype: dict mapping at most one org-id to
            at most BATCH_SIZE (dict) records
    """
    records = []
    current_owner_org = None

    with open(csv_path, 'rb') as f:
        first3bytes = f.read(3)
        if first3bytes != codecs.BOM_UTF8:
            f.seek(0)

        csv_in = DictReader(f)
        cols = csv_in.unicode_fieldnames

        expected = [f['datastore_id'] for f in chromo['fields']
            ] + ['owner_org', 'owner_org_title']
        assert cols == expected, 'column mismatch:\n{0}\n{1}'.format(
            cols, expected)

        none_fields = [f['datastore_id'] for f in chromo['fields']
            if f['datastore_type'] != 'text']

        for row_dict in csv_in:
            owner_org = row_dict.pop('owner_org')
            owner_org_title = row_dict.pop('owner_org_title')
            if owner_org != current_owner_org:
                if records:
                    yield (current_owner_org, records)
                records = []
                current_owner_org = owner_org

            for f_id in none_fields:
                if not row_dict[f_id]:
                    row_dict[f_id] = None

            records.append(row_dict)
            if len(records) >= BATCH_SIZE:
                yield (current_owner_org, records)
                records = []
    if records:
        yield (current_owner_org, records)
