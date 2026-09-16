// Run after experiment-highscores.js using gjs (no browser dependencies).
function assert(value) { if (!value) throw new Error('Assertion failed'); }
const rows = parseHistory('event_id,simulations,score,seed\n2,3,50,7\n9,8,12,8\n');
assert(rows.length === 2 && rows[1].score === 12);
assert(parseHistory('event_id,simulations,score,seed\n').length === 0);
for (const invalid of ['bad', 'event_id,simulations,score,seed\n1,2,3,<script>']) {
  let rejected = false;
  try { parseHistory(invalid); } catch (error) { rejected = true; }
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
  await drawHistory(rows, 10, chart, detail);
  const [scores, tail] = plotted.traces;
  assert(scores.line.shape === 'spline' && scores.line.smoothing === 1);
  assert(JSON.stringify(scores.x) === '[3,8]' && JSON.stringify(scores.y) === '[50,12]');
  assert(JSON.stringify(tail.x) === '[8,10]' && JSON.stringify(tail.y) === '[12,12]');
  assert(chart.removed === 'hidden' && plotted.config.responsive);
  chart.events.focus();
  assert(detail.textContent.includes('score: 50; seed: 7'));
  chart.events.keydown({key: 'ArrowRight', preventDefault() {}});
  assert(detail.textContent.includes('score: 12; seed: 8'));
  assert(hovered[0].pointNumber === 1);
  chart.events.plotly_hover({points: [{curveNumber: 0, pointNumber: 0}]});
  assert(detail.textContent.includes('score: 50; seed: 7'));
  await drawHistory([rows[0]], 3, chart, detail);
  assert(plotted.traces.length === 1 && plotted.traces[0].x.length === 1);
  print('Highscore CSV and Plotly checks passed');
}
const loop = new imports.gi.GLib.MainLoop(null, false);
let failure;
checkPlot().catch(error => {failure = error;}).finally(() => loop.quit());
loop.run();
if (failure) throw failure;
