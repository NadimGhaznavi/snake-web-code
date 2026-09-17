'use strict';
// RFC-style CSV: reasoning can contain commas, escaped quotes, and newlines.
function parseGoldenCSV(text) {
  const records = [];
  let row = [], field = '', quoted = false, closed = false;
  function endField() { row.push(field); field = ''; closed = false; }
  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    if (quoted) {
      if (char === '"') {
        if (text[i + 1] === '"') { field += '"'; i++; }
        else { quoted = false; closed = true; }
      } else field += char;
    } else if (char === ',') endField();
    else if (char === '\n' || char === '\r') {
      if (char === '\r' && text[i + 1] === '\n') i++;
      endField(); records.push(row); row = [];
    } else if (char === '"' && field === '' && !closed) quoted = true;
    else {
      if (closed || char === '"') throw new Error('Invalid CSV quoting');
      field += char;
    }
  }
  if (quoted) throw new Error('Unterminated CSV field');
  if (field || row.length || closed) { endField(); records.push(row); }
  const fields = ['event_id', 'occurred_at', 'run_id', 'high_score', 'parameter', 'change', 'reasoning'];
  if (JSON.stringify(records.shift()) !== JSON.stringify(fields)) throw new Error('Unexpected CSV schema');
  let previous = 0;
  return records.map(values => {
    if (values.length !== fields.length) throw new Error('Invalid CSV row');
    const entry = Object.fromEntries(fields.map((key, i) => [key, values[i]]));
    const id = Number(entry.event_id);
    if (!/^\d+$/.test(entry.event_id) || !Number.isSafeInteger(id) || id <= previous ||
        !/^\d*$/.test(entry.high_score)) throw new Error('Invalid golden record');
    previous = id;
    return entry;
  });
}

function renderGoldenRows(records, body) {
  const ordered = [...records].sort((a, b) =>
    b.occurred_at.localeCompare(a.occurred_at) || Number(b.event_id) - Number(a.event_id));
  for (const record of ordered) {
    const row = document.createElement('tr');
    const [date, time = ''] = record.occurred_at.split(/[ T]/);
    for (const [key, value] of [['date', date], ['time', time.split('.')[0]], ['config', record.run_id],
                                ['score', record.high_score], ['parameter', record.parameter],
                                ['change', record.change], ['reason', record.reasoning]]) {
      const cell = document.createElement('td');
      if (key === 'config' || key === 'reason') {
        if (value) {
          const link = document.createElement('a');
          link.textContent = key === 'config' ? 'JSON' : 'Thoughts';
          link.href = `golden-detail.html?event=${encodeURIComponent(record.event_id)}&view=${key}`;
          cell.appendChild(link);
        } else cell.textContent = '—';
      } else cell.textContent = value;
      row.appendChild(cell);
    }
    body.appendChild(row);
  }
}

async function loadGoldenHistory() {
  const message = document.getElementById('message');
  try {
    const response = await fetch('data/golden-configurations.csv', {cache: 'no-store'});
    if (!response.ok) throw new Error('CSV request failed');
    const records = parseGoldenCSV(await response.text());
    renderGoldenRows(records, document.getElementById('golden-rows'));
    message.textContent = records.length ? '' : 'No golden configurations recorded.';
    if (records.length) document.getElementById('golden-table').removeAttribute('hidden');
  } catch (error) {
    message.textContent = 'Unable to load golden configurations. Please reload to try again.';
  }
}
function renderGoldenDetail(record, view, simulations, detail) {
  if (view === 'reason') {
    detail.textContent = record.reasoning || 'No saved reasoning is available.';
  } else {
    const row = [...simulations].reverse().find(row => row.run_id === record.run_id);
    const configuration = row ? JSON.parse(row.detail).configuration : null;
    detail.textContent = configuration && Object.keys(configuration).length ?
      JSON.stringify(configuration, null, 2) : 'No saved configuration is available for this run.';
  }
}

async function loadGoldenDetail() {
  const message = document.getElementById('message');
  try {
    const params = new URLSearchParams(window.location.search);
    const view = params.get('view');
    if (!['config', 'reason'].includes(view)) throw new Error('Invalid detail view');
    const response = await fetch('data/golden-configurations.csv', {cache: 'no-store'});
    if (!response.ok) throw new Error('CSV request failed');
    const record = parseGoldenCSV(await response.text()).find(row => row.event_id === params.get('event'));
    if (!record) { message.textContent = 'Golden configuration not found.'; return; }
    let simulations = [];
    if (view === 'config') {
      const response = await fetch('data/event-simulations.csv', {cache: 'no-store'});
      if (!response.ok) throw new Error('Configuration request failed');
      simulations = parseReportCSV(await response.text(), ['run_id', 'detail']);
    }
    document.getElementById('title').textContent = view === 'config' ? 'Configuration JSON' : 'LLM Reasoning';
    renderGoldenDetail(record, view, simulations, document.getElementById('detail'));
    message.textContent = '';
  } catch (error) {
    message.textContent = 'Unable to load golden configuration details. Please reload to try again.';
  }
}

if (typeof document !== 'undefined') {
  if (document.body.dataset.page === 'detail') loadGoldenDetail();
  else loadGoldenHistory();
}
