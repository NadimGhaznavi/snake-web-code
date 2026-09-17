"""Generate and publish the complete current-experiment homepage."""

from datetime import datetime
from html import escape
import re
from pathlib import Path
import socket
from string import Template

from snake_web.activity.EventLogExport import export_event_log
from snake_web.activity.GoldenHistory import append_golden_history, read_golden_history
from snake_web.activity.HighscoreHistory import append_history, read_history
from snake_web.activity.RunScoreHistory import append_scores
from snake_web.activity.SimulationBoard import board_svg
from snake_web.activity.TopRuns import render_top_runs
from snake_web.entity.ExperimentStatus import ExperimentStatus


_TEMPLATE = Template(Path(__file__).with_name('homepage.html').read_text())


def render_status(status: ExperimentStatus, hostname: str, last_updated: str = '') -> str:
    def number(value, *, optional=False):
        if optional and value is None:
            return '—'
        if type(value) is not int or value < 0:
            raise ValueError('Experiment metrics must be nonnegative integers')
        return str(value)

    board = board_svg(status.snapshot)
    return _TEMPLATE.substitute(
        # Encode Liquid delimiters too: the file is processed by Jekyll after
        # publication, and hostnames are data, never template instructions.
        hostname=escape(hostname).replace('{', '&#123;').replace('}', '&#125;'),
        all_time_highscore=number(status.all_time_highscore, optional=True),
        current_highscore=number(status.current_highscore, optional=True),
        simulations=number(status.simulations_submitted),
        cycles=number(status.experiment_cycles),
        last_updated=escape(last_updated),
        board=board or '<p>No saved board is available for the current configuration.</p>',
    )


class PublishStatus:
    def __init__(self, appdb, publisher):
        self._appdb = appdb
        self._publisher = publisher

    def run(self) -> str:
        status = self._appdb.get_experiment_status()
        if status.all_time_highscore is None:
            return 'No recorded score; homepage preserved'
        with self._publisher.session():
            existing = self._publisher.read_history()
            history = read_history(existing)
            records = self._appdb.get_highscore_history(history[-1]['event_id'] if history else 0)
            csv_data = append_history(existing, records)
            scores = append_scores(self._publisher.read_history(self._publisher.SCORES_PATH),
                                   self._appdb.get_run_scores())
            golden_csv = self._publisher.read_history(self._publisher.GOLDEN_HISTORY_PATH)
            golden_rows = read_golden_history(golden_csv)
            golden_csv = append_golden_history(golden_csv, self._appdb.get_golden_configurations(
                int(golden_rows[-1]['event_id']) if golden_rows else 0))
            assets = Path(__file__).parent / 'reports'
            report = (assets / 'experiment-highscores.html').read_text().replace(
                '__TOTAL__', str(status.simulations_submitted))
            reports = {
                self._publisher.TOP_RUNS_PATH: render_top_runs(self._appdb.get_top_runs()),
                self._publisher.TOP_RUNS_SCRIPT_PATH: (assets / 'top-100.js').read_text(),
                self._publisher.GOLDEN_HISTORY_PATH: golden_csv,
                self._publisher.GOLDEN_PATH: (assets / 'golden-configurations.html').read_text(),
                self._publisher.GOLDEN_SCRIPT_PATH: (assets / 'golden-configurations.js').read_text(),
                self._publisher.SCORES_PATH: scores,
                self._publisher.DISTRIBUTION_PATH: (assets / 'score-distribution.html').read_text(),
                self._publisher.DISTRIBUTION_SCRIPT_PATH: (assets / 'score-distribution.js').read_text(),
                self._publisher.HISTORY_PATH: csv_data,
                self._publisher.REPORT_PATH: report,
                self._publisher.SCRIPT_PATH: (assets / 'experiment-highscores.js').read_text(),
            }
            reports.update(export_event_log(self._appdb, self._publisher))
            for path in (self._publisher.EVENT_PATH, self._publisher.EVENT_DETAIL_PATH,
                         self._publisher.EVENT_SCRIPT_PATH, self._publisher.CSV_SCRIPT_PATH):
                reports[path] = (assets / Path(path).name).read_text()
            previous_page = self._publisher.read_status()
            match = re.search(r'<!-- last-updated -->([^<]*)<!-- /last-updated -->', previous_page)
            previous_time = match.group(1) if match else ''
            page = render_status(status, socket.gethostname(), previous_time)
            if page != previous_page or any(
                    self._publisher.read_history(name) != content for name, content in reports.items()):
                page = render_status(status, socket.gethostname(),
                                     datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z (%z)'))
            changed = self._publisher.publish(page, reports)
        return f"Experiment homepage: {'published' if changed else 'unchanged'}"
