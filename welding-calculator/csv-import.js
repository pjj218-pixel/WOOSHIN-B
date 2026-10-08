(function (root) {
  const required = ['length', 'mode', 'speed', 'time', 'batch', 'nonArc', 'uptime', 'hours', 'days', 'months'];
  const shared = ['batch', 'nonArc', 'uptime', 'hours', 'days', 'months', 'vehicle', 'productName', 'process', 'equipment', 'gas'];
  const rowFields = ['materialA', 'thicknessA', 'materialB', 'thicknessB', 'joint', 'position'];

  function parseCsv(text) {
    const rows = [];
    let row = [];
    let cell = '';
    let quoted = false;
    text = text.replace(/^\uFEFF/, '');
    for (let i = 0; i < text.length; i++) {
      const char = text[i];
      if (char === '"') {
        if (quoted && text[i + 1] === '"') { cell += '"'; i++; }
        else quoted = !quoted;
      } else if (char === ',' && !quoted) {
        row.push(cell); cell = '';
      } else if ((char === '\n' || char === '\r') && !quoted) {
        if (char === '\r' && text[i + 1] === '\n') i++;
        row.push(cell);
        if (row.some(value => value.trim() !== '')) rows.push(row);
        row = []; cell = '';
      } else {
        cell += char;
      }
    }
    if (quoted) throw new Error('CSV의 따옴표가 닫히지 않았습니다.');
    row.push(cell);
    if (row.some(value => value.trim() !== '')) rows.push(row);
    return rows;
  }

  function parsePlanCsv(text) {
    const records = parseCsv(text);
    if (records.length < 2) throw new Error('CSV에 제목 행과 용접 구간을 한 개 이상 입력해 주세요.');
    const headers = records[0].map(value => value.trim());
    if (new Set(headers).size !== headers.length) throw new Error('CSV 제목에 중복된 항목이 있습니다.');
    const missing = required.filter(name => !headers.includes(name));
    if (missing.length) throw new Error(`CSV 제목에 필요한 항목이 없습니다: ${missing.join(', ')}`);
    const data = records.slice(1).map((record, index) => {
      if (record.length > headers.length) throw new Error(`${index + 2}행에 제목보다 많은 값이 있습니다.`);
      return Object.fromEntries(headers.map((header, column) => [header, (record[column] || '').trim()]));
    });
    data.slice(1).forEach((record, index) => {
      if (shared.some(name => record[name] && record[name] !== '')) throw new Error(`${index + 3}행의 생산 조건을 비워 주세요. 생산 조건은 첫 행에만 입력합니다.`);
    });
    return {
      rows: data.map(record => ({ length: record.length, mode: record.mode, speed: record.speed, time: record.time,
        ...Object.fromEntries(rowFields.map(name => [name, record[name] || ''])) })),
      ...Object.fromEntries(shared.map(name => [name, data[0][name] || ''])),
      sample: data[0].dataType === 'sample'
    };
  }

  const api = { parsePlanCsv };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.WeldCsv = api;
})(globalThis);
