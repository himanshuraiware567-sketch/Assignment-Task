from types import SimpleNamespace


class MockAirtableError(Exception):
    def __init__(self, message='mock Airtable error', status_code=None):
        super().__init__(message)
        self.response = SimpleNamespace(status_code=status_code, headers={})


class MockAirtableTable:
    """In-memory pyairtable-compatible table for export tests."""

    def __init__(self, failures=None):
        self.records = {}
        self.failures = failures or {}
        self.calls = []

    def batch_upsert(self, records, key_fields, typecast=False):
        self.calls.append({'records': records, 'key_fields': key_fields, 'typecast': typecast})
        created = []
        updated = []
        affected = []

        for record in records:
            fields = dict(record['fields'])
            key = tuple(fields[field] for field in key_fields)
            queued_failures = self.failures.get(key[0], [])
            if queued_failures:
                error = queued_failures.pop(0)
                raise error

            if key in self.records:
                airtable_id = self.records[key]['id']
                self.records[key]['fields'].update(fields)
                updated.append(airtable_id)
            else:
                airtable_id = f'rec{len(self.records) + 1}'
                self.records[key] = {'id': airtable_id, 'fields': fields}
                created.append(airtable_id)
            affected.append(self.records[key])

        return {
            'createdRecords': created,
            'updatedRecords': updated,
            'records': affected,
        }
