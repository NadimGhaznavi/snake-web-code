'use strict';
// RFC-style CSV: reasoning can contain commas, escaped quotes, and newlines.
function parseReportCSV(text, fields) {
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
  if (JSON.stringify(records.shift()) !== JSON.stringify(fields)) throw new Error('Unexpected CSV schema');
  return records.map(values => {
    if (values.length !== fields.length) throw new Error('Invalid CSV row');
    return Object.fromEntries(fields.map((key, i) => [key, values[i]]));
  });
}
