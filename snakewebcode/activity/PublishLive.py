"""Publish daily games, observed daily scores, and the cumulative histogram."""

from datetime import datetime
import json
from zoneinfo import ZoneInfo

from snakewebcode.activity.DailyGames import export_daily_games
from snakewebcode.activity.DailyProgress import export_daily_progress
from snakewebcode.activity.ScoreDistribution import render_distribution


class PublishLive:
    def __init__(self, appdb, publisher):
        self._appdb = appdb
        self._publisher = publisher

    def run(self, *, collect_progress=True):
        publisher = self._publisher
        with publisher.session():
            _, files = export_daily_games(self._appdb, publisher)
            state = json.loads(files.pop(publisher.DAILY_PATH))
            progress, progress_files = export_daily_progress(
                self._appdb, publisher, collect=collect_progress)
            files.update(progress_files)
            state['daily_progress'] = bool(progress_files)
            scores = {row['id']: row['high_score'] for row in self._appdb.get_run_scores()}
            files[publisher.DISTRIBUTION_PATH] = render_distribution(scores)
            changed = publisher.publish(
                state, files, updated=datetime.now(ZoneInfo('America/Toronto')).strftime('%Y-%m-%d %H:%M'))
            publisher.save_progress(progress)
        return f"Live artifacts: {'published' if changed else 'unchanged'}"
