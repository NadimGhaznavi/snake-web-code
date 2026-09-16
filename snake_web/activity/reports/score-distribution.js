/* Append-only observations; later rows replace earlier scores for the same run. */
'use strict';
function parseScores(csv) {
  const lines = csv.trim().split(/\r?\n/);
  if (lines.shift() !== 'id,high_score') throw new Error('Unexpected CSV schema');
  const latest = new Map();
  for (const line of lines) {
    const cells = line.split(',');
    if (cells.length !== 2 || !/^\d+$/.test(cells[0]) || !/^\d*$/.test(cells[1])) {
      throw new Error('Invalid score observation');
    }
    const id = Number(cells[0]);
    const score = cells[1] === '' ? null : Number(cells[1]);
    if (!Number.isSafeInteger(id) || id <= 0 || (score !== null && !Number.isSafeInteger(score))) {
      throw new Error('Invalid score value');
    }
    latest.set(id, score);
  }
  return [...latest.entries()].sort((a, b) => a[0] - b[0]).map(([id, score]) => ({id, score}));
}

function scoreDistribution(rows) {
  const half = Math.floor(rows.length / 2);
  const all = rows.filter(row => row.score !== null);
  const older = rows.slice(0, half).filter(row => row.score !== null);
  const result = {total: rows.length, half, scored: all.length, olderScored: older.length, bins: []};
  if (!all.length) return result;
  const low = all.reduce((value, row) => Math.min(value, row.score), Infinity);
  const high = all.reduce((value, row) => Math.max(value, row.score), 0);
  const size = Math.max(1, Math.ceil((high - low + 1) / 40));
  result.bins = Array.from({length: Math.floor((high - low) / size) + 1}, (_, index) => ({
    low: low + index * size, high: low + (index + 1) * size - 1, all: 0, older: 0,
  }));
  for (const row of all) result.bins[Math.floor((row.score - low) / size)].all++;
  for (const row of older) result.bins[Math.floor((row.score - low) / size)].older++;
  return result;
}

function drawDistribution(data, svg, detail) {
  const ns = 'http://www.w3.org/2000/svg';
  function add(tag, attrs, text) {
    const node = document.createElementNS(ns, tag);
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
    if (text !== undefined) node.textContent = text;
    svg.appendChild(node);
    return node;
  }
  const top = Math.max(1, ...data.bins.map(bin => bin.all));
  const width = 890 / data.bins.length;
  const y = value => 425 - value / top * 390;
  const ticks = Math.min(top, 5);
  for (let i = 0; i <= ticks; i++) {
    const value = Math.round(top * i / ticks);
    add('line', {x1: 80, x2: 970, y1: y(value), y2: y(value), stroke: '#40566e'});
    add('text', {x: 68, y: y(value)+5, fill: '#d5dfeb', 'text-anchor': 'end'}, String(value));
  }
  data.bins.forEach((bin, index) => {
    const label = bin.low === bin.high ? String(bin.low) : `${bin.low}–${bin.high}`;
    for (const [key, color, inset] of [['all', '#4c9be8', .04], ['older', '#f09445', .24]]) {
      if (!bin[key]) continue;
      const description = `Score: ${label}; All runs: ${bin.all}; Oldest half: ${bin.older}`;
      const bar = add('rect', {x: 80 + (index + inset) * width, y: y(bin[key]),
        width: width * (1 - 2 * inset), height: 425 - y(bin[key]), fill: color,
        tabindex: 0, 'aria-label': description});
      const title = document.createElementNS(ns, 'title');
      title.textContent = description;
      bar.appendChild(title);
      bar.addEventListener('mouseenter', () => { detail.textContent = description; });
      bar.addEventListener('focus', () => { detail.textContent = description; });
    }
    if (index % Math.ceil(data.bins.length / 8) === 0) {
      add('text', {x: 80 + (index + .5) * width, y: 452, fill: '#d5dfeb', 'text-anchor': 'middle'}, label);
    }
  });
  add('text', {x: 525, y: 488, fill: '#d5dfeb', 'text-anchor': 'middle'}, 'Run high score');
  add('text', {transform: 'translate(20 240) rotate(-90)', fill: '#d5dfeb', 'text-anchor': 'middle'}, 'Number of runs');
  svg.removeAttribute('hidden');
}

async function loadDistribution() {
  const message = document.getElementById('message');
  try {
    const response = await fetch('data/run-scores.csv', {cache: 'no-store'});
    if (!response.ok) throw new Error('CSV request failed');
    const data = scoreDistribution(parseScores(await response.text()));
    document.getElementById('summary').textContent =
      `All runs: ${data.total} (${data.scored} scored). Oldest half: ${data.half} (${data.olderScored} scored).`;
    message.textContent = data.scored ? '' : 'No scores recorded yet.';
    if (data.scored) drawDistribution(data, document.getElementById('chart'), document.getElementById('detail'));
  } catch (error) {
    message.textContent = 'Unable to load score history. Please reload to try again.';
  }
}
if (typeof document !== 'undefined') loadDistribution();
