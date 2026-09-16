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

async function drawHistory(rows, total, chart, detail) {
  const end = rows.reduce((max, row) => Math.max(max, row.simulations), Math.max(total, 1));
  const labels = rows.map(row =>
    `Simulations: ${row.simulations}; score: ${row.score}; seed: ${row.seed ?? 'unknown'}; event: ${row.id}`);
  const last = rows[rows.length - 1];
  const traces = [{
    type: 'scatter', mode: 'lines+markers',
    x: rows.map(row => row.simulations), y: rows.map(row => row.score),
    text: labels, hovertemplate: '%{text}<extra></extra>',
    line: {color: '#4c9be8', width: 3, shape: 'spline', smoothing: 1},
    marker: {color: '#f09445', size: 10},
  }];
  // Keep the final score level through the latest simulation count.
  if (end > last.simulations) traces.push({
    type: 'scatter', mode: 'lines',
    x: [last.simulations, end], y: [last.score, last.score],
    line: {color: '#4c9be8', width: 3}, hoverinfo: 'skip',
  });
  chart.removeAttribute('hidden');
  await Plotly.newPlot(chart, traces, {
    paper_bgcolor: '#151f2b', plot_bgcolor: '#151f2b',
    font: {color: '#d5dfeb', family: 'Courier New, monospace'},
    margin: {l: 80, r: 30, t: 30, b: 75}, showlegend: false,
    xaxis: {title: {text: 'Number of simulations'}, range: [0, end], gridcolor: '#40566e'},
    yaxis: {title: {text: 'Current config high score'}, rangemode: 'tozero', gridcolor: '#40566e'},
  }, {responsive: true, displaylogo: false});
  let selected = 0;
  function showPoint() {
    detail.textContent = labels[selected];
    Plotly.Fx.hover(chart, [{curveNumber: 0, pointNumber: selected}]);
  }
  chart.on('plotly_hover', event => {
    const point = event.points[0];
    if (point.curveNumber === 0) {
      selected = point.pointNumber;
      detail.textContent = labels[selected];
    }
  });
  chart.addEventListener('focus', showPoint);
  chart.addEventListener('keydown', event => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    if (event.key === 'Home') selected = 0;
    else if (event.key === 'End') selected = rows.length - 1;
    else selected = Math.max(0, Math.min(rows.length - 1,
      selected + (event.key === 'ArrowRight' ? 1 : -1)));
    showPoint();
  });
}

async function loadHistory() {
  const message = document.getElementById('message');
  try {
    const response = await fetch('data/experiment-highscores.csv', {cache: 'no-store'});
    if (!response.ok) throw new Error('CSV request failed');
    const rows = parseHistory(await response.text());
    message.textContent = rows.length ? '' : 'No accepted scores recorded yet.';
    if (rows.length) await drawHistory(rows, Number(document.getElementById('total').textContent),
      document.getElementById('chart'), document.getElementById('detail'));
  } catch (error) {
    message.textContent = 'Unable to load score history. Please reload to try again.';
  }
}
if (typeof document !== 'undefined') loadHistory();
if (typeof module !== 'undefined') module.exports = {parseHistory, drawHistory};
