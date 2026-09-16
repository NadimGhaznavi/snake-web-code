/* Numeric-only CSV contract: event_id,simulations,score,seed. */
'use strict';
function parseHistory(csv) {
  const lines = csv.trim().split(/\r?\n/);
  if (lines.shift() !== 'event_id,simulations,score,seed') throw new Error('Unexpected CSV schema');
  let previous = 0;
  return lines.map(line => {
    const cells = line.split(',');
    if (cells.length !== 4 || !cells.slice(0, 3).every(v => /^\d+$/.test(v)) ||
        !/^-?\d*$/.test(cells[3])) throw new Error('Invalid CSV record');
    const [id, simulations, score, seed] = cells.map(v => v === '' ? null : Number(v));
    if (![id, simulations, score].every(Number.isSafeInteger) ||
        (seed !== null && !Number.isSafeInteger(seed)) || id <= previous) throw new Error('Invalid CSV values');
    previous = id;
    return {id, simulations, score, seed};
  });
}

function drawHistory(rows, total, svg, detail) {
  const ns = 'http://www.w3.org/2000/svg';
  function add(tag, attrs, text) {
    const node = document.createElementNS(ns, tag);
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
    if (text !== undefined) node.textContent = text;
    svg.appendChild(node);
    return node;
  }
  const end = rows.reduce((max, row) => Math.max(max, row.simulations), Math.max(total, 1));
  const top = rows.reduce((max, row) => Math.max(max, row.score), 1);
  const x = value => 80 + value / end * 890;
  const y = value => 425 - value / top * 390;
  for (let i = 0; i <= 5; i++) {
    add('line', {x1: 80, x2: 970, y1: y(top*i/5), y2: y(top*i/5), stroke: '#40566e'});
    add('text', {x: 68, y: y(top*i/5)+5, fill: '#d5dfeb', 'text-anchor': 'end'}, String(Math.round(top*i/5)));
    add('text', {x: x(end*i/5), y: 452, fill: '#d5dfeb', 'text-anchor': 'middle'}, String(Math.round(end*i/5)));
  }
  add('text', {x: 525, y: 488, fill: '#d5dfeb', 'text-anchor': 'middle'}, 'Number of simulations');
  add('text', {transform: 'translate(20 240) rotate(-90)', fill: '#d5dfeb', 'text-anchor': 'middle'}, 'Current config high score');
  const points = rows.map(r => `${x(r.simulations)},${y(r.score)}`);
  points.push(`${x(end)},${y(rows[rows.length-1].score)}`);
  add('polyline', {points: points.join(' '), fill: 'none', stroke: '#4c9be8', 'stroke-width': 3});
  rows.forEach(row => {
    const label = `Simulations: ${row.simulations}; score: ${row.score}; seed: ${row.seed ?? 'unknown'}; event: ${row.id}`;
    const point = add('circle', {cx: x(row.simulations), cy: y(row.score), r: 5, fill: '#f09445', tabindex: 0, 'aria-label': label});
    const title = document.createElementNS(ns, 'title');
    title.textContent = label;
    point.appendChild(title);
    point.addEventListener('mouseenter', () => { detail.textContent = label; });
    point.addEventListener('focus', () => { detail.textContent = label; });
  });
  svg.removeAttribute('hidden');
}

async function loadHistory() {
  const message = document.getElementById('message');
  try {
    const response = await fetch('data/experiment-highscores.csv', {cache: 'no-store'});
    if (!response.ok) throw new Error('CSV request failed');
    const rows = parseHistory(await response.text());
    message.textContent = rows.length ? '' : 'No accepted scores recorded yet.';
    if (rows.length) drawHistory(rows, Number(document.getElementById('total').textContent),
      document.getElementById('chart'), document.getElementById('detail'));
  } catch (error) {
    message.textContent = 'Unable to load score history. Please reload to try again.';
  }
}
if (typeof document !== 'undefined') loadHistory();
if (typeof module !== 'undefined') module.exports = {parseHistory, drawHistory};
