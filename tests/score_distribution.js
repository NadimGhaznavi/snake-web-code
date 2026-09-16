// Run after score-distribution.js with gjs; no browser dependencies.
function assert(value) { if (!value) throw new Error('Assertion failed'); }
const rows = parseScores('id,high_score\n1,\n2,0\n3,10\n4,10\n5,100\n3,20\n');
assert(rows.length === 5 && rows[2].score === 20);
const data = scoreDistribution(rows);
assert(data.total === 5 && data.half === 2 && data.scored === 4 && data.olderScored === 1);
assert(data.bins.length === 34 && data.bins[0].low === 0 && data.bins[0].high === 2);
assert(data.bins[0].all === 1 && data.bins[0].older === 1);
assert(data.bins.reduce((sum, bin) => sum + bin.all, 0) === 4);
assert(data.bins.reduce((sum, bin) => sum + bin.older, 0) === 1);
assert(scoreDistribution(parseScores('id,high_score\n1,\n')).bins.length === 0);
assert(scoreDistribution([]).total === 0);
const same = scoreDistribution(parseScores('id,high_score\n2,7\n1,7\n3,7\n'));
assert(same.bins.length === 1 && same.bins[0].all === 3 && same.bins[0].older === 1);
for (const csv of ['bad', 'id,high_score\n1,-2\n', 'id,high_score\n1,<script>\n']) {
  let rejected = false;
  try { parseScores(csv); } catch (error) { rejected = true; }
  assert(rejected);
}
let plotted;
let hovered;
globalThis.Plotly = {
  newPlot(chart, traces, layout, config) {
    plotted = {traces, layout, config};
    return Promise.resolve();
  },
  Fx: {hover(chart, points) {hovered = points;}},
};
const detail = {};
const chart = {
  events: {},
  removeAttribute(key) {this.removed = key;},
  on(key, callback) {this.events[key] = callback;},
  addEventListener(key, callback) {this.events[key] = callback;},
};
async function checkPlot() {
  await drawDistribution(same, chart, detail);
  const [all, older] = plotted.traces;
  assert(all.type === 'bar' && older.type === 'bar');
  assert(all.x[0] === 7 && older.x[0] === 7);
  assert(all.y[0] === 3 && older.y[0] === 1);
  assert(all.width[0] > older.width[0] && plotted.layout.barmode === 'overlay');
  assert(chart.removed === 'hidden' && plotted.config.responsive);
  chart.events.focus();
  assert(detail.textContent === 'Score: 7; All runs: 3; Oldest half: 1');
  await drawDistribution(data, chart, detail);
  assert(plotted.traces[0].y.reduce((sum, value) => sum + value, 0) === 4);
  assert(plotted.traces[1].y.reduce((sum, value) => sum + value, 0) === 1);
  assert(plotted.traces[0].x.length === data.bins.length);
  assert(plotted.traces[0].x[0] === 1);
  chart.events.focus();
  assert(detail.textContent === 'Score: 0–2; All runs: 1; Oldest half: 1');
  chart.events.keydown({key: 'ArrowRight', preventDefault() {}});
  assert(detail.textContent === 'Score: 3–5; All runs: 0; Oldest half: 0');
  assert(hovered[0].pointNumber === 1);
  chart.events.keydown({key: 'End', preventDefault() {}});
  assert(hovered[0].pointNumber === data.bins.length - 1);
  chart.events.keydown({key: 'ArrowRight', preventDefault() {}});
  assert(hovered[0].pointNumber === data.bins.length - 1);
  chart.events.plotly_hover({points: [{curveNumber: 1, pointNumber: 0}]});
  assert(detail.textContent === 'Score: 0–2; All runs: 1; Oldest half: 1');
  Plotly.newPlot = () => Promise.reject(new Error('Render failed'));
  let rejected = false;
  try { await drawDistribution(data, chart, detail); } catch (error) { rejected = true; }
  assert(rejected);
  print('Histogram parsing, cohorts, bins, and Plotly checks passed');
}
const loop = new imports.gi.GLib.MainLoop(null, false);
let failure;
checkPlot().catch(error => {failure = error;}).finally(() => loop.quit());
loop.run();
if (failure) throw failure;
