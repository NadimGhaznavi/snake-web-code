'use strict';

function enableDailyGames(root) {
  const games = [...root.querySelectorAll('.daily-game')];
  const position = root.querySelector('[data-game-position]');
  let current = 0;
  let progress;

  function select(index, hold = false) {
    current = index;
    games.forEach((game, gameIndex) => { game.hidden = gameIndex !== current; });
    position.textContent = games.length ? `${current + 1} / ${games.length}` : '';
    if (progress) progress.select(games[current]?.dataset.gameId, hold);
  }

  const player = root.closest('.snake-experiment').querySelector('[data-progress]');
  if (player) {
    progress = enableDailyProgress(player, games.map(game => game.dataset.gameId), id => {
      const index = games.findIndex(game => game.dataset.gameId === id);
      if (index >= 0) select(index, true);
    });
  }
  root.querySelectorAll('[data-game-step]').forEach(button => {
    button.disabled = games.length < 2;
    button.addEventListener('click', () => {
      if (games.length < 2) return;
      select((current + Number(button.dataset.gameStep) + games.length) % games.length, true);
    });
  });
  select(0);
}

function enableDailyProgress(player, gameIds, onSelect) {
  const data = JSON.parse(player.dataset.progress);
  const frames = data.frames;
  const columns = Math.min(4, frames.length);
  const available = new Set(gameIds);
  const namespace = 'http://www.w3.org/2000/svg';
  function element(name, attributes, parent) {
    const node = document.createElementNS(namespace, name);
    Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, String(value)));
    parent.append(node);
    return node;
  }
  const chart = element('svg', {viewBox: '0 0 800 438', class: 'progress-chart',
    role: 'group', 'aria-label': 'Daily configuration scores; select a bar to display its game'}, player);
  chart.setAttribute('hidden', '');
  const background = element('image', {href: data.sprite, width: columns * 800,
    height: Math.ceil(frames.length / columns) * 438, 'aria-hidden': 'true'}, chart);
  const highlight = element('rect', {fill: '#f09445', 'pointer-events': 'none'}, chart);
  const controls = [];
  for (let slot = 0; slot < 10; slot++) {
    const control = element('rect', {class: 'progress-bar', fill: 'transparent'}, chart);
    control.addEventListener('focus', () => {
      holding = true;
      clearTimeout(timer);
    });
    control.addEventListener('click', () => {
      if (available.has(control.dataset.gameId)) onSelect(control.dataset.gameId);
    });
    control.addEventListener('keydown', event => {
      if ((event.key === 'Enter' || event.key === ' ') && available.has(control.dataset.gameId)) {
        event.preventDefault();
        onSelect(control.dataset.gameId);
      }
    });
    controls.push(control);
  }
  let current = 0;
  let selected;
  let timer;
  let holding = false;

  function rows(index) {
    return [...frames[index].configurations].sort((a, b) => a.high_score - b.high_score || b.id - a.id);
  }

  function draw() {
    background.setAttribute('x', -(current % columns) * 800);
    background.setAttribute('y', -Math.floor(current / columns) * 438);
    const configurations = rows(current);
    const slots = Array(10 - configurations.length).fill(null).concat(configurations);
    highlight.setAttribute('visibility', 'hidden');
    controls.forEach((control, slot) => {
      const row = slots[slot];
      if (!row) {
        control.setAttribute('visibility', 'hidden');
        control.removeAttribute('tabindex');
        delete control.dataset.gameId;
        return;
      }
      const id = String(row.id);
      const x = 111 + slot * 70;
      const height = 270 * row.high_score / data.ceiling;
      const y = 328 - height;
      const playable = available.has(id);
      control.dataset.gameId = id;
      control.setAttribute('visibility', 'visible');
      control.setAttribute('x', x - 35);
      control.setAttribute('y', Math.max(0, y - 42));
      control.setAttribute('width', 70);
      control.setAttribute('height', height + 65);
      control.setAttribute('role', playable ? 'button' : 'img');
      control.setAttribute('aria-label', `Simulation #${id}, high score ${row.high_score}${playable ? '' : ', not in the daily game viewer'}`);
      if (playable) {
        control.setAttribute('tabindex', 0);
        control.setAttribute('aria-pressed', id === selected);
      } else {
        control.removeAttribute('tabindex');
        control.removeAttribute('aria-pressed');
      }
      if (id === selected) {
        highlight.setAttribute('x', x - 24);
        highlight.setAttribute('y', row.high_score ? y : 324);
        highlight.setAttribute('width', 49);
        highlight.setAttribute('height', Math.max(4, height));
        highlight.setAttribute('visibility', 'visible');
      }
    });
  }

  function advance() {
    if (holding || document.hidden) return;
    draw();
    timer = setTimeout(() => {
      current = (current + 1) % frames.length;
      advance();
    }, current === frames.length - 1 ? 5000 : 2000);
  }

  const sprite = new Image();
  sprite.onload = () => {
    player.querySelector('img').hidden = true;
    chart.removeAttribute('hidden');
    draw();
    advance();
  };
  sprite.onerror = () => chart.remove(); // Keep the original GIF if its frame sheet is unavailable.
  sprite.src = data.sprite;
  document.addEventListener('visibilitychange', () => {
    clearTimeout(timer);
    if (!holding) advance();
  });
  return {
    select(id, hold) {
      const focused = chart.contains(document.activeElement);
      selected = id;
      if (hold) {
        holding = true;
        clearTimeout(timer);
        for (let index = frames.length - 1; index >= 0; index--) {
          if (frames[index].configurations.some(row => String(row.id) === id)) {
            current = index;
            break;
          }
        }
      }
      draw();
      if (hold && focused) controls.find(control => control.dataset.gameId === id)?.focus();
    },
  };
}

if (typeof document !== 'undefined') {
  document.querySelectorAll('.daily-games').forEach(enableDailyGames);
}
