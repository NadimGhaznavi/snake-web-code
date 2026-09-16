"""Append observations of mutable run scores; publish only ID and score."""

import csv
import io


FIELDS = ('id', 'high_score')


def read_scores(content):
    """Return the latest observation per run, including unscored submissions."""
    if not content:
        return {}
    reader = csv.reader(io.StringIO(content))
    if next(reader, None) != list(FIELDS):
        raise ValueError('Unexpected run score CSV schema')
    latest = {}
    for record in reader:
        if len(record) != 2:
            raise ValueError('Invalid run score record')
        run_id, score = record
        if not run_id.isascii() or not run_id.isdecimal() or int(run_id) <= 0:
            raise ValueError('Invalid run ID')
        if score and (not score.isascii() or not score.isdecimal()):
            raise ValueError('Invalid run score')
        latest[int(run_id)] = int(score) if score else None
    return latest


def append_scores(content, records):
    latest = read_scores(content)
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, lineterminator='\n')
    if not content:
        writer.writerow(FIELDS)
    elif not content.endswith('\n'):
        raise ValueError('Run score CSV must end with a newline')
    for row in records:
        run_id, score = row['id'], row['high_score']
        if type(run_id) is not int or run_id <= 0 or (
                score is not None and (type(score) is not int or score < 0)):
            raise ValueError('Invalid run score observation')
        if run_id not in latest or latest[run_id] != score:
            writer.writerow((run_id, score))
            latest[run_id] = score
    return content + stream.getvalue()
