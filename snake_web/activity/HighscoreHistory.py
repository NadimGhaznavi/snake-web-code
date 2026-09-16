"""Incremental, deliberately numeric public data for the highscore plot."""

import csv
import io


FIELDS = ('event_id', 'simulations', 'score', 'seed')


def read_history(content):
    if not content:
        return []
    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames != list(FIELDS):
        raise ValueError('Unexpected highscore CSV schema')
    rows = []
    previous = 0
    for record in reader:
        row = {key: None if key == 'seed' and record[key] == '' else int(record[key])
               for key in FIELDS}
        if row['event_id'] <= previous or row['simulations'] < 0 or row['score'] < 0:
            raise ValueError('Invalid highscore history ordering or metrics')
        previous = row['event_id']
        rows.append(row)
    return rows


def append_history(content, records):
    """Preserve existing records; reject duplicates or malformed new rows."""
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator='\n')
    if not content:
        writer.writeheader()
    for row in records:
        writer.writerow({key: row[key] for key in FIELDS})
    result = content + stream.getvalue()
    read_history(result)
    return result
