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
const elements = [];
globalThis.document = {createElementNS(ns, tag) {
  return {tag, attrs: {}, events: {}, children: [],
    setAttribute(key, value) {this.attrs[key] = value;},
    appendChild(child) {this.children.push(child);},
    addEventListener(key, callback) {this.events[key] = callback;}};
}};
const detail = {};
const svg = {appendChild(node) {elements.push(node);}, removeAttribute(key) {this.removed = key;}};
drawDistribution(same, svg, detail);
const bars = elements.filter(node => node.tag === 'rect');
assert(bars.length === 2 && bars[0].attrs.height === 390 && bars[1].attrs.height === 130);
bars[1].events.focus();
assert(detail.textContent === 'Score: 7; All runs: 3; Oldest half: 1');
assert(svg.removed === 'hidden');
print('Histogram parsing, cohorts, bins, and rendering checks passed');
