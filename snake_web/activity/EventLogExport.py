"""Export only approved events and public detail fields, before publication."""

import base64
import csv
import io
import json
import re

from snake_web.activity.GoldenHistory import reasoning_content
from snake_web.activity.SimulationBoard import board_svg
from snake_web.constants.PublicEvents import EVENT_LABELS

EVENT_FIELDS = ('event_id', 'occurred_at', 'category', 'name', 'log_level',
                'process_id', 'source_name', 'parameter', 'parent_event_id', 'ax3l_version', 'detail')
SIMULATION_FIELDS = ('run_id', 'detail')
# Prompt PNGs can exceed csv's small default limit; fail rather than truncate.
csv.field_size_limit(64 * 1024 * 1024)


def read_csv(content, fields):
    if not content:
        return []
    reader = csv.DictReader(io.StringIO(content, newline=''), strict=True)
    if reader.fieldnames != list(fields):
        raise ValueError('Unexpected public event CSV schema')
    rows = list(reader)
    if any(set(row) != set(fields) or None in row.values() for row in rows):
        raise ValueError('Invalid public event CSV record')
    return rows


def append_csv(content, fields, rows):
    if content and not content.endswith('\n'):
        raise ValueError('Public event CSV must end with a newline')
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
    if not content:
        writer.writeheader()
    writer.writerows(rows)
    return content + stream.getvalue()


def prompt_parts(content):
    try:
        value = json.loads(content)['content']
    except (TypeError, ValueError, KeyError):
        raise ValueError('Invalid stored prompt; export stopped') from None
    if isinstance(value, str):
        return [{'type': 'text', 'text': value}]
    if not isinstance(value, list):
        raise ValueError('Invalid stored prompt content')
    parts = []
    for part in value:
        if isinstance(part, dict) and part.get('type') == 'text' and isinstance(part.get('text'), str):
            parts.append({'type': 'text', 'text': part['text']})
        elif isinstance(part, dict) and part.get('type') == 'image_url':
            image = part.get('image_url')
            url = image.get('url') if isinstance(image, dict) else None
            if not isinstance(url, str) or not re.fullmatch(r'data:image/png;base64,[A-Za-z0-9+/]+={0,2}', url):
                raise ValueError('Only embedded PNG prompt images may be exported')
            parts.append({'type': 'image', 'url': url})
        else:
            raise ValueError('Unsupported prompt part; export stopped')
    return parts


def numeric_metrics(value, prefix=''):
    """Keep numeric usage/timing leaves, including nested token counts."""
    result = {}
    if isinstance(value, dict):
        for key, child in value.items():
            path = f'{prefix}.{key}' if prefix else key
            if type(child) in (int, float):
                result[path] = child
            elif isinstance(child, dict):
                result.update(numeric_metrics(child, path))
    return result


def sanitize_event(record):
    kind = (record['category'], record['name'])
    if kind not in EVENT_LABELS:
        raise ValueError('Event is not on the public allowlist')
    content = record.get('content')
    if kind == ('Conversation', 'reply_received'):
        # No response envelope, choices, assistant content, or tool arguments.
        detail = {'reasoning': reasoning_content(content)}
        try:
            response = json.loads(content)
        except (TypeError, ValueError):
            response = {}
        # Preserve numeric usage/timing metrics; discard arbitrary nested payloads.
        for section in ('usage', 'timings'):
            metrics = response.get(section) if isinstance(response, dict) else None
            if isinstance(metrics, dict):
                detail[section] = numeric_metrics(metrics)
    elif kind == ('Conversation', 'prompt_sent'):
        detail = {'parts': prompt_parts(content)}
    elif kind[0] == 'SnakeLab':
        detail = {'message': str(content or EVENT_LABELS[kind])}
    else:
        detail = {'message': str(content or '')}
    row = {key: str(record.get(key) or '') for key in EVENT_FIELDS if key != 'detail'}
    row['detail'] = json.dumps(detail, ensure_ascii=False, allow_nan=False)
    return row


def simulation_detail(record):
    svg = board_svg(record.get('high_score_snapshot'))
    return json.dumps({
        'run_id': record['run_id'], 'project_version': record.get('project_version'),
        'high_score': record.get('high_score'),
        'completed_at': str(record['completed_at']) if record.get('completed_at') else None,
        'board': 'data:image/svg+xml;base64,' + base64.b64encode(svg.encode()).decode() if svg else None,
        'configuration': record.get('configuration') or {},
    }, ensure_ascii=False, allow_nan=False)


def export_event_log(appdb, publisher):
    """Append events through a snapshot boundary and refresh mutable run details."""
    content = publisher.read_history(publisher.EVENT_HISTORY_PATH)
    old_events = read_csv(content, EVENT_FIELDS)
    previous = 0
    run_ids = set()
    for event in old_events:
        event_id = int(event['event_id'])
        if event_id <= previous or (event['category'], event['name']) not in EVENT_LABELS:
            raise ValueError('Invalid public event history')
        previous = event_id
        if event['category'] == 'SnakeLab' and event['process_id']:
            run_ids.add(event['process_id'])
    saved = publisher.read_history(publisher.EVENT_CURSOR_PATH)
    cursor = json.loads(saved) if saved else {'version': 1, 'through_event_id': previous}
    if (cursor.get('version') != 1 or type(cursor.get('through_event_id')) is not int
            or cursor['through_event_id'] < previous):
        raise ValueError('Invalid event export cursor')
    end = appdb.get_event_export_end()
    if end < cursor['through_event_id']:
        raise ValueError('Source event history reset; refusing to reuse published history')
    after = cursor['through_event_id']
    rows = []
    while after < end:
        batch = appdb.get_public_events(after, end)
        if not batch:
            break
        for event in batch:
            if not after < event['event_id'] <= end:
                raise ValueError('Invalid event export ordering')
            rows.append(sanitize_event(event))
            after = event['event_id']
            if event['category'] == 'SnakeLab' and event.get('process_id'):
                run_ids.add(event['process_id'])
    content = append_csv(content, EVENT_FIELDS, rows)
    simulations = publisher.read_history(publisher.EVENT_SIMULATIONS_PATH)
    latest = {row['run_id']: row['detail'] for row in read_csv(simulations, SIMULATION_FIELDS)}
    changes = []
    ordered_ids = sorted(run_ids)
    for offset in range(0, len(ordered_ids), 250):
        for record in appdb.get_public_simulations(ordered_ids[offset:offset + 250]):
            detail = simulation_detail(record)
            if latest.get(record['run_id']) != detail:
                changes.append({'run_id': record['run_id'], 'detail': detail})
                latest[record['run_id']] = detail
    return {
        publisher.EVENT_HISTORY_PATH: content,
        publisher.EVENT_SIMULATIONS_PATH: append_csv(simulations, SIMULATION_FIELDS, changes),
        publisher.EVENT_CURSOR_PATH: json.dumps({'version': 1, 'through_event_id': end}) + '\n',
    }
