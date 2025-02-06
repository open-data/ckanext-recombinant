from unicodecsv import DictReader
import codecs

from typing import Any, Dict, Generator, Tuple, List, Optional


BATCH_SIZE = 15000


def csv_data_batch(csv_path: str,
                   chromo: Dict[str, Any],
                   strict: bool = True) -> Generator[
                       Tuple[Optional[str], List[Dict[str, Any]]], None, None]:
    """
    Generator of dataset records from csv file

    :param csv_path: file to parse
    :param chromo: recombinant resource definition
    :param strict: True to fail on header mismatch

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
        cols = []
        if csv_in.fieldnames:
            cols = [
                f for f in csv_in.fieldnames
                if f not in chromo.get('csv_org_extras', [])]

        if strict:
            expected = [f['datastore_id'] for f in chromo['fields'] if not f.get(
                'published_resource_computed_field')]
            assert cols == expected, 'column mismatch:\n{0}\n{1}'.format(
                cols, expected)

        none_fields = [f['datastore_id'] for f in chromo['fields']
                       if f['datastore_type'] != 'text']

        for row_dict in csv_in:
            owner_org = row_dict.pop('owner_org', None)
            if owner_org != current_owner_org:
                if records:
                    yield (current_owner_org, records)
                records = []
                current_owner_org = owner_org

            for f_id in none_fields:
                if not row_dict.get(f_id, ''):
                    row_dict[f_id] = None

            for f in chromo['fields']:
                if f.get('published_resource_computed_field'):
                    row_dict.pop(f['datastore_id'], None)

            records.append(row_dict)
            if len(records) >= BATCH_SIZE:
                yield (current_owner_org, records)
                records = []
    if records:
        yield (current_owner_org, records)
