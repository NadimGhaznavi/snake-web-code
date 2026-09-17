// Run after golden-configurations.js using gjs.
function assert(value) { if (!value) throw new Error('Assertion failed'); }
const header = 'event_id,occurred_at,run_id,high_score,parameter,change,reasoning\n';
const records = parseGoldenCSV(header + '1,2026-09-16 12:00:00,baseline,0,,,\n' +
  '3,2026-09-16 13:00:00,winner,8,"Epsilon: initial, decay","1 > 0.5, 0.9 > 0.8","Consider ""this"", then\n<script>literal</script>"\n');
assert(records.length === 2 && records[1].reasoning === 'Consider "this", then\n<script>literal</script>');
assert(parseGoldenCSV(header).length === 0);
for (const csv of ['bad', header + '1,a,b,0,,,"unterminated', header + '1,a,b,0,,,\n1,a,b,0,,,\n']) {
  let rejected = false;
  try { parseGoldenCSV(csv); } catch (error) { rejected = true; }
  assert(rejected);
}
globalThis.document = {createElement(tag) {
  return {tag, children: [], appendChild(child) {this.children.push(child);},
          set innerHTML(value) {throw new Error('Unsafe HTML insertion');}};
}};
const body = document.createElement('tbody');
renderGoldenRows(records, body);
assert(body.children.length === 2);
const configLink = body.children[0].children[2].children[0];
assert(configLink.textContent === 'JSON' && configLink.href === 'golden-detail.html?event=3&view=config');
assert(body.children[1].children[3].textContent === '0');
const reasonLink = body.children[0].children[6].children[0];
assert(reasonLink.tag === 'a' && reasonLink.textContent === 'Thoughts');
assert(reasonLink.href === 'golden-detail.html?event=3&view=reason');
assert(body.children[1].children[6].children.length === 0);
const detail = document.createElement('pre');
renderGoldenDetail(records[1], 'reason', [], detail);
assert(detail.textContent === records[1].reasoning);
renderGoldenDetail(records[0], 'reason', [], detail);
assert(detail.textContent.includes('No saved reasoning'));
const simulations = [
  {run_id: 'winner', detail: JSON.stringify({configuration: {seed: 1}})},
  {run_id: 'unrelated', detail: JSON.stringify({configuration: {seed: 999}})},
  {run_id: 'winner', detail: JSON.stringify({configuration: {seed: 2, training: {gamma: .9}}})},
];
renderGoldenDetail(records[1], 'config', simulations, detail);
assert(detail.textContent === JSON.stringify({seed: 2, training: {gamma: .9}}, null, 2));
renderGoldenDetail(records[0], 'config', simulations, detail);
assert(detail.textContent.includes('No saved configuration'));
print('Golden CSV quoting, ordering, and safe rendering checks passed');
