"""Save observed half-hour rankings and render the day's configuration progress."""

from datetime import date, datetime, timedelta
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


RENDERER_VERSION = 3
FONT = Path(__file__).parent / 'fonts' / 'DejaVuSansMono.ttf'
MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
          'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')


def observation_slot(now):
    """The midnight publication closes the preceding day's 48th interval."""
    slot = now.hour * 2 + now.minute // 30 - 1
    return (now.date() - timedelta(days=1), 47) if slot < 0 else (now.date(), slot)


def configuration_record(row):
    if (type(row['id']) is not int or row['id'] < 1
            or type(row['high_score']) is not int or row['high_score'] < 0):
        raise ValueError('Invalid daily configuration ID or score')
    return dict(id=row['id'], high_score=row['high_score'])


def read_progress(content):
    if not content:
        return None
    state = json.loads(content)
    if (not isinstance(state, dict) or state.get('version') != 1
            or type(state.get('renderer')) is not int
            or not isinstance(state.get('frames'), list) or not 1 <= len(state['frames']) <= 48):
        raise ValueError('Invalid daily progress state')
    day = date.fromisoformat(state['day'])
    previous_slot = -1
    for frame in state['frames']:
        if (not isinstance(frame, dict) or type(frame.get('slot')) is not int
                or not previous_slot < frame['slot'] < 48
                or not isinstance(frame.get('configurations'), list)
                or len(frame['configurations']) > 10):
            raise ValueError('Invalid daily progress frame')
        observed_at = datetime.fromisoformat(frame['observed_at'])
        if observation_slot(observed_at) != (day, frame['slot']):
            raise ValueError('Daily progress timestamp differs from slot')
        rows = [configuration_record(row) for row in frame['configurations']]
        if (len({row['id'] for row in rows}) != len(rows)
                or rows != sorted(rows, key=lambda row: (-row['high_score'], row['id']))):
            raise ValueError('Invalid daily configuration ordering')
        previous_slot = frame['slot']
    return state


def render_progress(state):
    """Use ten fixed slots and one zero-based scale for every observed frame."""
    maximum = max((row['high_score'] for frame in state['frames']
                   for row in frame['configurations']), default=0)
    ceiling = max(50, ((maximum + 9) // 10) * 10)
    fonts = {size: ImageFont.truetype(str(FONT), size) for size in (24, 28, 32)}
    images = []
    for frame in state['frames']:
        image = Image.new('RGB', (800, 480), '#101720')
        draw = ImageDraw.Draw(image)
        draw.text((24, 60), 'High score', font=fonts[28], fill='#a7b8cb')
        for tick in range(6):
            value = ceiling * tick // 5
            y = 370 - 270 * value / ceiling
            draw.line((76, y, 776, y), fill='#303d4b')
            draw.text((66, y), str(value), anchor='rm', font=fonts[28], fill='#a7b8cb')
        draw.line((76, 100, 76, 370), fill='#a7b8cb')
        draw.line((76, 370, 776, 370), fill='#a7b8cb')
        rows = sorted(frame['configurations'], key=lambda row: (row['high_score'], -row['id']))
        slots = [None] * (10 - len(rows)) + rows
        for index, row in enumerate(slots):
            x = 111 + index * 70
            if row is None:
                draw.text((x, 390), '—', anchor='mm', font=fonts[24], fill='#66717e')
                continue
            y = 370 - 270 * row['high_score'] / ceiling
            if row['high_score']:
                draw.rectangle((x - 24, y, x + 24, 369), fill='#79b8f3')
            draw.text((x, y - 8), str(row['high_score']), anchor='mb',
                      font=fonts[32], fill='#d5dfeb')
            draw.text((x, 390), str(row['id']), anchor='mm', font=fonts[24], fill='#a7b8cb')
        draw.text((426, 420), 'Configuration (simulation ID)', anchor='mm',
                  font=fonts[24], fill='#a7b8cb')
        observed_at = datetime.fromisoformat(frame['observed_at'])
        timestamp = (f'{observed_at:%d} {MONTHS[observed_at.month - 1]} '
                     f'{observed_at:%Y - %H:%M}')
        draw.text((24, 450), timestamp, font=fonts[24], fill='#a7b8cb')
        images.append(image.crop((0, 42, 800, 480)))
    output = BytesIO()
    images[0].save(output, format='GIF', save_all=True, append_images=images[1:],
                   duration=[2000] * (len(images) - 1) + [5000], loop=0, disposal=2)
    return output.getvalue()


def export_daily_progress(appdb, publisher, *, collect=True):
    state = read_progress(publisher.read_history(publisher.PROGRESS_PATH))
    if not collect and state is None:
        return '', {}
    changed = False
    if collect:
        now = appdb.get_daily_progress_time()
        day, slot = observation_slot(now)
        if state and day < date.fromisoformat(state['day']):
            raise ValueError('Daily progress source clock moved backwards')
        if not state or state['day'] != day.isoformat():
            state = dict(version=1, renderer=RENDERER_VERSION, day=day.isoformat(), frames=[])
        if state['frames'] and slot < state['frames'][-1]['slot']:
            raise ValueError('Daily progress source clock moved backwards')
        changed = not state['frames'] or slot != state['frames'][-1]['slot']
        if changed:
            rows = [configuration_record(row) for row in appdb.get_daily_configurations(day, now)]
            state['frames'].append(dict(slot=slot, observed_at=now.isoformat(), configurations=rows))
    regenerate = changed or state['renderer'] != RENDERER_VERSION
    state['renderer'] = RENDERER_VERSION
    content = json.dumps(state, indent=2) + '\n'
    read_progress(content)
    data = publisher.read_bytes(publisher.PROGRESS_GIF_PATH)
    if regenerate or not data.startswith((b'GIF87a', b'GIF89a')):
        data = render_progress(state)
    token = sha256(data).hexdigest()[:16]
    html = (f'<img class="progress-chart" src="{publisher.PROGRESS_GIF_PATH}?v={token}" '
            'alt="Animated top ten configuration scores, lowest to highest, '
            f'for {state["day"]}; {len(state["frames"])} observed half-hour updates.">')
    return html, {publisher.PROGRESS_PATH: content, publisher.PROGRESS_GIF_PATH: data}
