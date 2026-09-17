"""Render the current top 100 simulations using validated saved boards."""

from pathlib import Path
from string import Template

from snake_web.activity.SimulationBoard import board_svg


_TEMPLATE = Template(Path(__file__).with_name('reports').joinpath('top-100.html').read_text())


def render_top_runs(rows: list[dict]) -> str:
    sections = []
    for index, row in enumerate(rows):
        run_id, score = row['id'], row['high_score']
        if type(run_id) is not int or run_id <= 0 or type(score) is not int or score < 0:
            raise ValueError('Invalid top simulation ID or score')
        board = board_svg(row.get('high_score_snapshot'))
        board = board or '<p>No saved board is available for this simulation.</p>'
        previous = (index - 1) % len(rows) + 1
        following = (index + 1) % len(rows) + 1
        sections.append(
            f'<section class="ranked-run" id="rank-{index + 1}" tabindex="-1" '
            f'aria-label="Rank {index + 1} of {len(rows)}">\n'
            f'<div class="board">{board}</div>\n'
            f'<nav aria-label="Ranked simulations">'
            f'<button type="button" data-rank="{previous}" aria-label="Previous ranked simulation" disabled>&lt;</button>'
            f'<span>Run #{run_id} - Score: {score}</span>'
            f'<button type="button" data-rank="{following}" aria-label="Next ranked simulation" disabled>&gt;</button>'
            f'</nav>\n</section>'
        )
    return _TEMPLATE.substitute(
        runs='\n'.join(sections) or '<p>No scored simulations recorded yet.</p>')
