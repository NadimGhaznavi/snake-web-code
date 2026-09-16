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
assert(body.children[0].children[2].textContent === 'winner');
assert(body.children[1].children[3].textContent === '0');
const details = body.children[0].children[6].children[0];
assert(details.tag === 'details' && details.children[1].tag === 'pre');
assert(details.children[1].textContent === records[1].reasoning);
assert(body.children[1].children[6].children.length === 0);
print('Golden CSV quoting, ordering, and safe rendering checks passed');
