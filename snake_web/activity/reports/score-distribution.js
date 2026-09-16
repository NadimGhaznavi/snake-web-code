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

async function drawDistribution(data, chart, detail) {
  const labels = data.bins.map(bin => bin.low === bin.high ? String(bin.low) : `${bin.low}–${bin.high}`);
  const descriptions = data.bins.map((bin, index) =>
    `Score: ${labels[index]}; All runs: ${bin.all}; Oldest half: ${bin.older}`);
  const centers = data.bins.map(bin => (bin.low + bin.high) / 2);
  // Plot precomputed counts so both cohorts retain exactly the same bins.
  const traces = [['all', 'All runs', '#4c9be8', .92],
                  ['older', 'Oldest half', '#f09445', .52]].map(([key, name, color, width]) => ({
    type: 'bar', name, x: centers, y: data.bins.map(bin => bin[key]),
    width: data.bins.map(bin => (bin.high - bin.low + 1) * width),
    marker: {color}, text: descriptions, textposition: 'none',
    hovertemplate: '%{text}<extra></extra>',
  }));
  chart.removeAttribute('hidden');
  await Plotly.newPlot(chart, traces, {
    barmode: 'overlay', paper_bgcolor: '#151f2b', plot_bgcolor: '#151f2b',
    font: {color: '#d5dfeb', family: 'Courier New, monospace'},
    margin: {l: 65, r: 20, t: 65, b: 75},
    legend: {orientation: 'h', x: 0, y: 1.15},
    xaxis: {title: {text: 'Run high score'}, gridcolor: '#40566e', automargin: true},
    yaxis: {title: {text: 'Number of runs'}, rangemode: 'tozero',
            tickformat: ',d', gridcolor: '#40566e', automargin: true},
  }, {responsive: true, displaylogo: false});
  let selected = 0;
  function showBin() {
    detail.textContent = descriptions[selected];
    Plotly.Fx.hover(chart, [{curveNumber: 0, pointNumber: selected}]);
  }
  chart.on('plotly_hover', event => {
    selected = event.points[0].pointNumber;
    detail.textContent = descriptions[selected];
  });
  chart.addEventListener('focus', showBin);
  chart.addEventListener('keydown', event => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    if (event.key === 'Home') selected = 0;
    else if (event.key === 'End') selected = data.bins.length - 1;
    else selected = Math.max(0, Math.min(data.bins.length - 1,
      selected + (event.key === 'ArrowRight' ? 1 : -1)));
    showBin();
  });
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
    if (data.scored) await drawDistribution(data, document.getElementById('chart'), document.getElementById('detail'));
  } catch (error) {
    message.textContent = 'Unable to load score history. Please reload to try again.';
  }
}
if (typeof document !== 'undefined') loadDistribution();
