from unicodecsv import DictReader

BATCH_SIZE = 1000
UTF8_BOM = u'\uFEFF'.encode(u'utf-8')


def csv_data_batch(csv_path, chromo):
    """
    Generator of dataset records from csv file

    :param csv_path: file to parse
    :param chromo: recombinant resource definition

    Yields a batch of records for at most one organization
    as (org_id, org_name, list of record dicts)
    """
    records = []
    current_owner_org = (None, None)

    with open(csv_path, 'rb') as f:
        bom = f.read(len(UTF8_BOM))
        assert bom == UTF8_BOM, 'file missing expected UTF-8 BOM'
        csv_in = DictReader(f)
        cols = csv_in.unicode_fieldnames

        expected = [f['datastore_id'] for f in chromo['fields']
            ] + ['owner_org_id', 'owner_org_name', 'owner_org_title']
        assert cols == expected, 'column mismatch:\n{0}\n{1}'.format(
            cols, expected)

        for row_dict in csv_in:
            owner_org_id = row_dict.pop('owner_org_id')
            owner_org_name = row_dict.pop('owner_org_name')
            owner_org_title = row_dict.pop('owner_org_title')
            if owner_org_id != current_owner_org_id:
                if records:
                    yield current_owner_org + (records,)
                records = []
                current_owner_org = (owner_org_id, owner_org_name)

            records.append(row_dict)
            if len(records) >= BATCH_SIZE:
                yield current_owner_org + (records,)
                records = []
    if records:
        yield current_owner_org + (records,)
