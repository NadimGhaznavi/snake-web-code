// Run after report-csv.js and event-log.js using gjs.
function assert(value) { if (!value) throw new Error('Assertion failed'); }
function csvCell(value) { return '"' + String(value).replaceAll('"', '""') + '"'; }
const responseDetail = {reasoning: 'Reason "one",\n<script>literal</script>', usage: {prompt_tokens: 12}, timings: {predicted_ms: 2}};
const values = ['4', '2026-09-16 12:00:00', 'Conversation', 'reply_received', 'INFO', 'conversation', '', '', '1', '1.0', JSON.stringify(responseDetail)];
const csv = EVENT_FIELDS.join(',') + '\n' + values.map(csvCell).join(',') + '\n';
const response = parseEvents(csv)[0];
assert(response.detail.reasoning === responseDetail.reasoning);
assert(parseEvents(EVENT_FIELDS.join(',') + '\n').length === 0);
let rejected = false;
try { parseEvents(csv + values.map(csvCell).join(',') + '\n'); } catch (_) { rejected = true; }
assert(rejected);
assert(prettyText('{"seed":1}').includes('\n  "seed": 1'));
assert(prettyText('Config: {"seed":1}').includes('\n  "seed": 1'));
assert(prettyText('Plain text <script>') === 'Plain text <script>');
function node(tag) {
  return {tag, textContent: '', children: [], events: {}, value: '', disabled: false,
    appendChild(child) { this.children.push(child); },
    replaceChildren() { this.children = []; },
    addEventListener(key, handler) { this.events[key] = handler; },
    set innerHTML(value) { throw new Error('Unsafe HTML insertion'); }};
}
const ids = {};
for (const id of ['category', 'event', 'search', 'events', 'count', 'previous', 'next']) ids[id] = node(id);
globalThis.document = {createElement: node, getElementById(id) {return ids[id];}};
const detail = node('main');
renderEventDetail(response, detail);
assert(detail.children[0].textContent === 'LLM reasoning');
assert(detail.children[1].tag === 'pre' && detail.children[1].textContent === responseDetail.reasoning);
assert(!detail.children.some(child => ['Response', 'Choices'].includes(child.textContent)));
const prompt = {...response, name: 'prompt_sent', detail: {parts: [
  {type: 'text', text: '{"seed":1}'}, {type: 'image', url: 'https://unsafe/image.png'},
  {type: 'image', url: 'data:image/png;base64,YQ=='},
]}};
const promptView = node('main'); renderEventDetail(prompt, promptView);
assert(promptView.children.filter(child => child.tag === 'img').length === 1);
assert(promptView.children[1].textContent.includes('\n  "seed": 1'));
const run = {run_id: 'run-1', project_version: '1.0', high_score: 0, completed_at: null, board: null, configuration: {seed: 1}};
const runView = node('main'); renderSimulation(run, runView, false);
assert(runView.children[0].textContent === 'High-score Board');
const configView = node('main'); renderSimulation(run, configView, true);
assert(configView.children[2].tag === 'pre');
assert(detailURL({...response, category: 'SnakeLab', name: 'simulation_submitted', process_id: 'run &1'}) ===
  'event-detail.html?run=run%20%261&view=config');
assert(detailURL(response) === 'event-detail.html?event=4');
const events = Array.from({length: 205}, (_, i) => ({...response, event_id: String(i + 1)}));
setupEventList(events);
assert(ids.events.children.length === 100 && ids.previous.disabled && !ids.next.disabled);
ids.next.events.click();
assert(ids.events.children.length === 100 && !ids.previous.disabled);
ids.next.events.click();
assert(ids.events.children.length === 5 && ids.next.disabled);
ids.search.value = 'no match'; ids.search.events.input();
assert(ids.events.children.length === 0 && ids.count.textContent === 'No matching events.');
ids.search.value = ''; ids.search.events.input();
ids.category.value = 'SnakeLab'; ids.category.events.input();
assert(ids.events.children.length === 0);
ids.category.value = ''; ids.category.events.input();
ids.event.value = 'Conversation/reply_received'; ids.event.events.input();
assert(ids.events.children.length === 100);
print('Event log CSV, sanitization display, JSON formatting, links, filters, and pagination checks passed');
