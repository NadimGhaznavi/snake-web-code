'use strict';
const EVENT_FIELDS = ['event_id', 'occurred_at', 'category', 'name', 'log_level', 'process_id', 'source_name', 'parameter', 'parent_event_id', 'ax3l_version', 'detail'];
const EVENT_LABELS = {
  'SnakeLab/simulation_completed': 'Simulation Completed',
  'Configuration/golden_config_retained': 'Golden Retained',
  'Conversation/prompt_sent': 'Prompt',
  'Conversation/reply_received': 'Response',
  'SnakeLab/simulation_submitted': 'Simulation Submitted',
};
function parseEvents(csv) {
  let previous = 0;
  return parseReportCSV(csv, EVENT_FIELDS).map(row => {
    const id = Number(row.event_id);
    if (!Number.isSafeInteger(id) || id <= previous || !EVENT_LABELS[`${row.category}/${row.name}`]) {
      throw new Error('Invalid public event history');
    }
    previous = id;
    return {...row, label: EVENT_LABELS[`${row.category}/${row.name}`], detail: JSON.parse(row.detail)};
  });
}
function element(tag, text, parent) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (parent) parent.appendChild(node);
  return node;
}
function prettyText(text) {
  try { return JSON.stringify(JSON.parse(text), null, 2); } catch (_) { /* ordinary prompt text */ }
  // Prompt prose often precedes a one-line JSON object or array.
  return text.split('\n').map(line => {
    const index = line.search(/[\[{]/);
    if (index < 0) return line;
    try { return line.slice(0, index) + JSON.stringify(JSON.parse(line.slice(index)), null, 2); }
    catch (_) { return line; }
  }).join('\n');
}
function showFields(parent, values) {
  const table = element('table', undefined, parent);
  for (const [key, value] of Object.entries(values)) {
    const row = element('tr', undefined, table);
    const label = element('th', key.replaceAll('_', ' '), row);
    label.scope = 'row';
    element('td', value === null || value === '' ? '—' : String(value), row);
  }
}
function showPrompt(parent, parts) {
  for (const part of parts) {
    if (part.type === 'text') element('pre', prettyText(part.text), parent);
    else if (part.type === 'image' && /^data:image\/png;base64,[A-Za-z0-9+/]+={0,2}$/.test(part.url)) {
      const image = element('img', undefined, parent);
      image.src = part.url; image.alt = 'Plot captured in prompt';
    }
  }
}
function renderEventDetail(event, parent) {
  if (event.name === 'reply_received') {
    element('h2', 'LLM reasoning', parent);
    element('pre', event.detail.reasoning || 'No reasoning recorded.', parent);
  } else if (event.name === 'prompt_sent') {
    element('h2', 'Prompt sent to the LLM', parent);
    showPrompt(parent, event.detail.parts);
  } else element('pre', event.detail.message || '', parent);
  element('h2', 'Event', parent);
  showFields(parent, Object.fromEntries(EVENT_FIELDS.filter(key => key !== 'detail').map(key => [key, event[key]])));
  for (const section of ['usage', 'timings']) {
    if (event.detail[section] && Object.keys(event.detail[section]).length) {
      element('h2', section === 'usage' ? 'Usage' : 'Timings', parent);
      showFields(parent, event.detail[section]);
    }
  }
}
function renderSimulation(run, parent, configuration) {
  if (configuration) {
    element('h2', 'Configuration', parent);
    element('p', `Run ID: ${run.run_id}`, parent);
    if (Object.keys(run.configuration).length) element('pre', JSON.stringify(run.configuration, null, 2), parent);
    else element('p', 'No saved configuration is available for this run.', parent);
    return;
  }
  element('h2', 'High-score Board', parent);
  if (run.board && /^data:image\/svg\+xml;base64,[A-Za-z0-9+/]+={0,2}$/.test(run.board)) {
    const image = element('img', undefined, parent);
    image.src = run.board; image.alt = 'High-score Board'; image.className = 'board';
  } else element('p', 'No saved board is available for this run.', parent);
  showFields(parent, {'Run ID': run.run_id, 'Project Version': run.project_version,
    'High Score': run.high_score, 'Completed At': run.completed_at});
}
function eventSummary(event) {
  if (event.name === 'prompt_sent') return event.detail.parts.filter(part => part.type === 'text').map(part => part.text).join('\n') || 'View plot prompt';
  if (event.name === 'reply_received') return event.detail.reasoning || 'No reasoning recorded';
  return event.detail.message || event.label;
}
function detailURL(event) {
  if (event.category === 'SnakeLab' && event.process_id) {
    return `event-detail.html?run=${encodeURIComponent(event.process_id)}` +
      (event.name === 'simulation_submitted' ? '&view=config' : '');
  }
  return `event-detail.html?event=${encodeURIComponent(event.event_id)}`;
}
function setupEventList(events) {
  const category = document.getElementById('category');
  const type = document.getElementById('event');
  const search = document.getElementById('search');
  for (const value of [...new Set(events.map(event => event.category))].sort()) element('option', value, category).value = value;
  for (const [key, value] of Object.entries(EVENT_LABELS)) element('option', value, type).value = key;
  const ordered = [...events].sort((a, b) => b.occurred_at.localeCompare(a.occurred_at) || Number(b.event_id) - Number(a.event_id));
  let page = 0;
  const size = 100;
  function render() {
    const query = search.value.toLowerCase();
    const filtered = ordered.filter(event => (!category.value || event.category === category.value) &&
      (!type.value || `${event.category}/${event.name}` === type.value) &&
      (!query || [event.process_id, event.parameter, event.source_name, eventSummary(event)].join(' ').toLowerCase().includes(query)));
    page = Math.min(page, Math.max(0, Math.ceil(filtered.length / size) - 1));
    const body = document.getElementById('events'); body.replaceChildren();
    for (const event of filtered.slice(page * size, (page + 1) * size)) {
      const row = element('tr', undefined, body);
      for (const key of ['occurred_at', 'event_id', 'log_level', 'category', 'label', 'parameter']) element('td', event[key], row);
      const cell = element('td', undefined, row);
      const summary = eventSummary(event);
      element('a', summary.slice(0, 180) + (summary.length > 180 ? '…' : ''), cell).href = detailURL(event);
    }
    document.getElementById('count').textContent = filtered.length ?
      `${page * size + 1}–${Math.min((page + 1) * size, filtered.length)} of ${filtered.length} matching events (${events.length} total)` : 'No matching events.';
    document.getElementById('previous').disabled = page === 0;
    document.getElementById('next').disabled = (page + 1) * size >= filtered.length;
  }
  for (const control of [category, type, search]) control.addEventListener('input', () => { page = 0; render(); });
  document.getElementById('previous').addEventListener('click', () => { page--; render(); });
  document.getElementById('next').addEventListener('click', () => { page++; render(); });
  render();
}
async function fetchCSV(path) {
  const response = await fetch(path, {cache: 'no-store'});
  if (!response.ok) throw new Error('CSV request failed');
  return response.text();
}
async function loadEventLog() {
  const message = document.getElementById('message');
  try {
    if (document.body.dataset.page === 'list') {
      const events = parseEvents(await fetchCSV('data/events.csv'));
      setupEventList(events);
      message.textContent = events.length ? '' : 'No public events recorded yet.';
    } else {
      const params = new URLSearchParams(window.location.search);
      const parent = document.getElementById('detail');
      if (params.has('run')) {
        const rows = parseReportCSV(await fetchCSV('data/event-simulations.csv'), ['run_id', 'detail']);
        const row = rows.reverse().find(row => row.run_id === params.get('run'));
        if (!row) { message.textContent = 'Simulation details are not available in this export.'; return; }
        const config = params.get('view') === 'config';
        document.getElementById('title').textContent = config ? 'Simulation Configuration' : 'Simulation Run';
        renderSimulation(JSON.parse(row.detail), parent, config);
        const link = element('a', config ? 'Simulation Run' : 'Configuration', parent);
        link.href = `event-detail.html?run=${encodeURIComponent(row.run_id)}` + (config ? '' : '&view=config');
      } else {
        const events = parseEvents(await fetchCSV('data/events.csv'));
        const event = events.find(row => row.event_id === params.get('event'));
        if (!event) { message.textContent = 'Event not found in the public log.'; return; }
        document.getElementById('title').textContent = `${event.label}${event.source_name ? ` (${event.source_name})` : ''}: #${event.event_id}`;
        renderEventDetail(event, parent);
      }
      message.textContent = '';
    }
  } catch (error) {
    message.textContent = 'Unable to load the event log. Please reload to try again.';
  }
}
if (typeof document !== 'undefined') loadEventLog();
