def csv_data_batch(csv_path, target_dataset):
    """
    Generator of dataset records from csv file

    :param csv_path: file to parse

    :return a batch of records for at most one organization
    :rtype: dict mapping at most one org-id to
            at most BATCH_SIZE (dict) records
    """
    records = []
    current_owner_org = None

    firstpart, filename = os.path.split(csv_path)
    assert filename.endswith('.csv')

    chromo = get_chromo(filename[:-4])

    with open(csv_path) as f:
        csv_in = DictReader(f)
        cols = csv_in.unicode_fieldnames

        expected = [f['datastore_id'] for f in chromo['resources']]
        assert cols[:-2] == expected, 'column mismatch:\n{0}\n{1}'.format(
            cols[:-2], expected)

        for row_dict in csv_in:
            owner_org = row_dict.pop('owner_org')
            owner_org_title = row_dict.pop('owner_org_title')
            if owner_org != current_owner_org:
                if records:
                    yield (current_owner_org, records)
                records = []
                current_owner_org = owner_org

            row_dict = dict((k, safe_for_solr(v)) for k, v in row_dict.items())
            records.append(row_dict)
            if len(records) >= BATCH_SIZE:
                yield (current_owner_org, records)
                records = []
    yield records
