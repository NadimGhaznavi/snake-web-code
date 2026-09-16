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
const elements = [];
globalThis.document = {createElementNS(ns, tag) {
  return {tag, attrs: {}, events: {}, children: [],
    setAttribute(key, value) {this.attrs[key] = value;},
    appendChild(child) {this.children.push(child);},
    addEventListener(key, callback) {this.events[key] = callback;}};
}};
const detail = {};
const svg = {appendChild(node) {elements.push(node);}, removeAttribute(key) {this.removed = key;}};
drawHistory(rows, 10, svg, detail);
const line = elements.find(node => node.tag === 'polyline');
assert(line.attrs.points === '347,35 792,331.4 970,331.4');
const dots = elements.filter(node => node.tag === 'circle');
assert(dots.length === 2 && svg.removed === 'hidden');
dots[1].events.focus();
assert(detail.textContent.includes('score: 12; seed: 8'));
print('Highscore CSV and plot checks passed');
