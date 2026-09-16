"""Generate and publish the complete current-experiment homepage."""

from html import escape
from pathlib import Path
import socket
from string import Template

from snake_web.activity.SimulationBoard import board_svg
from snake_web.entity.ExperimentStatus import ExperimentStatus


_TEMPLATE = Template(Path(__file__).with_name('homepage.html').read_text())


def render_status(status: ExperimentStatus, hostname: str) -> str:
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
            changed = self._publisher.publish(render_status(status, socket.gethostname()))
        return f"Experiment homepage: {'published' if changed else 'unchanged'}"
