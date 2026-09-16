"""Incremental golden history with a strict public-field allowlist."""

import csv
import io
import json

from snake_web.activity.GoldenConfigurations import parameter_change
from snake_web.constants.ReportLabels import FIELD_TO_LABEL_MAP

FIELDS = ('event_id', 'occurred_at', 'run_id', 'high_score', 'parameter', 'change', 'reasoning')


def reasoning_content(content):
    try:
        value = json.loads(content)['choices'][0]['message'].get('reasoning_content')
    except (TypeError, ValueError, KeyError, IndexError, AttributeError):
        return ''
    return value if isinstance(value, str) else ''


def read_golden_history(content):
    if not content:
        return []
    reader = csv.DictReader(io.StringIO(content, newline=''), strict=True)
    if reader.fieldnames != list(FIELDS):
        raise ValueError('Unexpected golden history CSV schema')
    rows, previous = [], 0
    for row in reader:
        if set(row) != set(FIELDS) or any(value is None for value in row.values()):
            raise ValueError('Invalid golden history record')
        event_id = int(row['event_id'])
        if event_id <= previous or (row['high_score'] and int(row['high_score']) < 0):
            raise ValueError('Invalid golden history ordering or score')
        previous = event_id
        rows.append(row)
    return rows


def append_golden_history(content, records):
    read_golden_history(content)
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator='\n')
    if not content:
        writer.writeheader()
    elif not content.endswith('\n'):
        raise ValueError('Golden history CSV must end with a newline')
    for record in records:
        parameter = record.get('parameter') or ''
        writer.writerow(dict(
            event_id=record['event_id'], occurred_at=record.get('occurred_at') or '',
            run_id=record.get('process_id') or '', high_score=record.get('high_score'),
            parameter=FIELD_TO_LABEL_MAP.get(parameter, parameter),
            change=parameter_change(record.get('decision'), parameter),
            reasoning=reasoning_content(record.get('response')),
        ))
    result = content + stream.getvalue()
    read_golden_history(result)
    return result
