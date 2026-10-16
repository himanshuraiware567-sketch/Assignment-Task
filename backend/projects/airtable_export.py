import os
import time

import requests
from pyairtable import Api


class AirtableConfigurationError(Exception):
    pass


def create_airtable_table():
    """Create a real Airtable table client from server-side environment settings."""
    api_key = os.environ.get('AIRTABLE_API_KEY')
    base_id = os.environ.get('AIRTABLE_BASE_ID')
    table_name = os.environ.get('AIRTABLE_TABLE_NAME')
    if not all((api_key, base_id, table_name)):
        raise AirtableConfigurationError(
            'AIRTABLE_API_KEY, AIRTABLE_BASE_ID, and AIRTABLE_TABLE_NAME must be configured'
        )

    # Retries are handled per task below so a failed task does not abort the export.
    return Api(api_key, retry_strategy=None).table(base_id, table_name)


def _status_code(error):
    response = getattr(error, 'response', None)
    return getattr(response, 'status_code', None)


def _retry_after(error, fallback):
    response = getattr(error, 'response', None)
    headers = getattr(response, 'headers', {}) or {}
    try:
        return max(0, float(headers.get('Retry-After', fallback)))
    except (TypeError, ValueError):
        return fallback


def _retryable(error):
    if isinstance(error, (requests.ConnectionError, requests.Timeout)):
        return True
    return _status_code(error) in (408, 429, 500, 502, 503, 504)


def export_tasks(tasks, table, *, max_retries=3, sleeper=None):
    """Upsert each task independently and return per-record export counts."""
    sleeper = sleeper or time.sleep
    result = {'created': 0, 'updated': 0, 'failed': 0, 'failures': []}

    for task in tasks:
        fields = {
            'Task ID': str(task.id),
            'Title': task.title,
            'Description': task.description or '',
            'Status': task.status,
            'Position': task.position,
            'Project': task.project.name,
            'Assignee': task.assignee.name if task.assignee else '',
            'Created By': task.created_by.name,
        }
        record = {'fields': fields}

        for attempt in range(max_retries + 1):
            try:
                upsert = table.batch_upsert([record], key_fields=['Task ID'], typecast=True)
                if upsert.get('createdRecords'):
                    result['created'] += 1
                elif upsert.get('updatedRecords'):
                    result['updated'] += 1
                else:
                    raise RuntimeError('Airtable did not report this record as created or updated')
                break
            except Exception as error:
                if _retryable(error) and attempt < max_retries:
                    fallback = 30 if _status_code(error) == 429 else 0.5 * (2 ** attempt)
                    sleeper(_retry_after(error, fallback))
                    continue

                result['failed'] += 1
                result['failures'].append({
                    'taskId': str(task.id),
                    'error': str(error)[:300] or error.__class__.__name__,
                })
                break

    return result
