"""Select three captured games and publish their flat-file state with the GIFs."""

from datetime import date
import json
import logging
from uuid import UUID

import zmq

from snake_web.activity.SimulationAnimation import SimulationAnimation
from snake_web.interface.SnakeLab import SnakeLab


DURATION_MS = 75


def game_record(row):
    if (type(row['id']) is not int or row['id'] < 1
            or type(row['high_score']) is not int or row['high_score'] < 0):
        raise ValueError('Invalid daily simulation ID or score')
    return dict(id=row['id'], run_id=str(UUID(row['run_id'])), high_score=row['high_score'])


def read_daily_state(content):
    if not content:
        return None
    state = json.loads(content)
    if (not isinstance(state, dict) or state.get('version') != 1
            or type(state.get('renderer')) is not int or type(state.get('duration_ms')) is not int
            or not isinstance(state.get('games'), list)
            or len(state['games']) > 3):
        raise ValueError('Invalid daily games state')
    date.fromisoformat(state['day'])
    games = [game_record(row) for row in state['games']]
    if (len({row['run_id'] for row in games}) != len(games)
            or games != sorted(games, key=lambda row: (-row['high_score'], row['id']))):
        raise ValueError('Invalid daily game ordering')
    return state


def export_daily_games(appdb, publisher, snake=None):
    day = appdb.get_daily_game_day()
    previous = read_daily_state(publisher.read_history(publisher.DAILY_PATH))
    cache = {}
    if (previous and previous['day'] == day.isoformat()
            and previous['renderer'] == SimulationAnimation.VERSION
            and previous['duration_ms'] == DURATION_MS):
        for rank, row in enumerate(previous['games']):
            data = publisher.read_bytes(publisher.DAILY_GIF_PATHS[rank])
            if data.startswith((b'GIF87a', b'GIF89a')):
                cache[(row['run_id'], row['high_score'])] = data
    snake = snake or SnakeLab()
    games, files = [], {}
    unavailable = False
    for row in appdb.get_daily_runs(day):
        game = game_record(row)
        animation = cache.get((game['run_id'], game['high_score']))
        if animation is None and not unavailable:
            try:
                frames = snake.get_highscore_frames(game['run_id'])
            except zmq.ZMQError:
                logging.exception('Snake Lab captures unavailable; retaining cached daily games')
                unavailable = True
                frames = None
            if frames is not None:
                if frames[-1]['board']['score'] != game['high_score']:
                    raise ValueError('Captured game score differs from simulation result')
                animation = SimulationAnimation.render(frames, DURATION_MS)
        if animation is None:
            continue  # Legacy SVG-only games never qualify.
        files[publisher.DAILY_GIF_PATHS[len(games)]] = animation
        games.append(game)
        if len(games) == 3:
            break
    state = dict(version=1, day=day.isoformat(), renderer=SimulationAnimation.VERSION,
                 duration_ms=DURATION_MS, games=games)
    files[publisher.DAILY_PATH] = json.dumps(state, indent=2) + '\n'
    return games, files


def render_daily_games(games):
    figures = []
    for rank, row in enumerate(games, 1):
        game = game_record(row)
        url = (f'reports/games/daily-{rank}.gif?run={game["run_id"]}'
               f'&amp;renderer={SimulationAnimation.VERSION}&amp;score={game["high_score"]}')
        figures.append(
            f'<figure class="daily-game"{ " hidden" if rank > 1 else ""}>'
            f'<img class="simulation-board" src="{url}" '
            f'alt="Animated game from simulation {game["id"]}">'
            f'<figcaption>Simulation #{game["id"]} - Highscore {game["high_score"]}</figcaption>'
            '</figure>')
    return '\n'.join(figures)
