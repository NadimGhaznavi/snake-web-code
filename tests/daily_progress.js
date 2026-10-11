// Run in a browser with the publisher's real frame sheet in window.progressFixture.
async function testDailyProgress() {
  const scheduled = [];
  const originalTimeout = window.setTimeout;
  const originalClear = window.clearTimeout;
  window.setTimeout = (callback, duration) => {
    const entry = {callback, duration, cancelled: false};
    scheduled.push(entry);
    return entry;
  };
  window.clearTimeout = entry => { if (entry) entry.cancelled = true; };
  const wait = () => new Promise(resolve => originalTimeout(resolve, 10));
  const ensure = (value, message) => { if (!value) throw new Error(message); };
  try {
    for (const count of [0, 1, 2, 3, 10]) {
      const experiment = document.createElement('section');
      experiment.className = 'snake-experiment';
      const root = document.createElement('section');
      root.className = 'daily-games';
      root.innerHTML = Array.from({length: count}, (_, index) =>
        `<figure class="daily-game" data-game-id="${index + 1}"${index ? ' hidden' : ''}></figure>`).join('') +
        '<span data-game-position></span><button data-game-step="-1"></button><button data-game-step="1"></button>';
      experiment.append(root);
      const player = document.createElement('div');
      player.dataset.progress = JSON.stringify(window.progressFixture);
      player.innerHTML = '<img alt="GIF fallback">';
      experiment.append(player);
      document.body.append(experiment);
      enableDailyGames(root);
      const chart = player.querySelector('svg');
      for (let attempt = 0; chart.hasAttribute('hidden') && attempt < 200; attempt++) await wait();
      ensure(!chart.hasAttribute('hidden'), 'Frame sheet did not load');
      ensure(player.querySelector('img').hidden, 'GIF fallback still visible');
      const highlight = chart.querySelector('rect[fill="#f09445"]');
      const position = root.querySelector('[data-game-position]');
      const previous = root.querySelector('[data-game-step="-1"]');
      const next = root.querySelector('[data-game-step="1"]');
      const visible = () => [...root.querySelectorAll('.daily-game')].filter(game => !game.hidden);
      const bar = id => chart.querySelector(`.progress-bar[data-game-id="${id}"]`);
      const selected = id => {
        ensure(visible().length === 1 && visible()[0].dataset.gameId === String(id), 'Wrong visible game');
        ensure(bar(id).getAttribute('aria-pressed') === 'true', 'Selected bar not marked');
        ensure(highlight.getAttribute('visibility') === 'visible', 'Orange highlight missing');
        ensure(Number(highlight.getAttribute('x')) === Number(bar(id).getAttribute('x')) + 11,
          'Highlight belongs to a different bar');
      };
      ensure(previous.disabled === (count < 2) && next.disabled === (count < 2), 'Arrow availability');
      if (!count) {
        ensure(visible().length === 0 && highlight.getAttribute('visibility') === 'hidden', 'Empty viewer');
        ensure(chart.querySelectorAll('[role="button"]').length === 0, 'Unavailable bars selectable');
      } else {
        selected(1);
        if (count > 1) {
          previous.click();
          selected(count);
          ensure(position.textContent === `${count} / ${count}`, 'Previous arrow position');
          next.click();
          selected(1);
          const bounds = bar(count).getBoundingClientRect();
          const target = document.elementFromPoint(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2);
          ensure(target === bar(count), 'Pointer hit target differs from the displayed bar');
          target.dispatchEvent(new MouseEvent('click', {bubbles: true}));
          selected(count);
          ensure(position.textContent === `${count} / ${count}`, 'Click did not synchronize navigation');
          bar(1).dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true}));
          selected(1);
          bar(count).dispatchEvent(new KeyboardEvent('keydown', {key: ' ', bubbles: true}));
          selected(count);
          for (let index = 0; index < count; index++) next.click();
          selected(count);
          ensure(scheduled.at(-1).cancelled, 'Navigation did not hold the selected frame');
        }
        if (count < 10) {
          const before = position.textContent;
          bar(10).dispatchEvent(new MouseEvent('click', {bubbles: true}));
          ensure(position.textContent === before, 'Unavailable capture changed selection');
          ensure(bar(10).getAttribute('role') === 'img', 'Unavailable bar exposed as a button');
        }
      }
      experiment.remove();
    }
    // Playback uses the original two-second/five-second timing until navigation.
    ensure(scheduled.some(entry => entry.duration === 2000), 'Two-second frames missing');
    const initial = scheduled.find(entry => !entry.cancelled);
    initial.callback();
    ensure(scheduled.at(-1).duration === 5000, 'Final frame hold missing');
    const failure = document.createElement('section');
    failure.className = 'snake-experiment';
    failure.innerHTML = '<section class="daily-games"><figure class="daily-game" data-game-id="1"></figure>' +
      '<figure class="daily-game" data-game-id="2" hidden></figure><span data-game-position></span>' +
      '<button data-game-step="1"></button></section><div data-progress><img alt="GIF fallback"></div>';
    failure.querySelector('[data-progress]').dataset.progress = JSON.stringify({
      ...window.progressFixture, sprite: 'missing-frame-sheet.png',
    });
    document.body.append(failure);
    enableDailyGames(failure.querySelector('.daily-games'));
    for (let attempt = 0; failure.querySelector('svg') && attempt < 200; attempt++) await wait();
    ensure(!failure.querySelector('svg') && !failure.querySelector('img').hidden, 'Failed sheet did not retain the GIF');
    failure.querySelector('button').click();
    ensure(failure.querySelector('[data-game-position]').textContent === '2 / 2', 'Fallback broke arrow navigation');
    failure.remove();
  } finally {
    window.setTimeout = originalTimeout;
    window.clearTimeout = originalClear;
  }
  return 'Arrow/bar selection, pointer targets, orange highlights, keyboard navigation, empty/single/2/3/10 games, frame timing, and GIF fallback passed';
}
