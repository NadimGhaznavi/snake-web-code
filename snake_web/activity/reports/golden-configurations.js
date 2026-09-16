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
    for (const value of [date, time.split('.')[0], record.run_id, record.high_score,
                         record.parameter, record.change]) {
      const cell = document.createElement('td');
      cell.textContent = value;
      row.appendChild(cell);
    }
    const reason = document.createElement('td');
    if (record.reasoning) {
      const details = document.createElement('details');
      const summary = document.createElement('summary');
      summary.textContent = 'Reason';
      const pre = document.createElement('pre');
      pre.textContent = record.reasoning;
      details.appendChild(summary); details.appendChild(pre); reason.appendChild(details);
    }
    row.appendChild(reason); body.appendChild(row);
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
if (typeof document !== 'undefined') loadGoldenHistory();
