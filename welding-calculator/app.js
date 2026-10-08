const form = document.getElementById('calculator');
const error = document.getElementById('error');
const result = document.getElementById('result');
const rowsContainer = document.getElementById('weld-rows');
const sampleButton = document.getElementById('sample-button');
const addButton = document.getElementById('add-row');
const fileInput = document.getElementById('csv-file');
const fileStatus = document.getElementById('file-status');
const formatter = new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 2 });
let source = 'user';
let hasCalculated = false;
let importedName = '';

const example = {
  rows: [
    { length: 600, mode: 'speed', speed: 300, materialA: '409', thicknessA: 1.5, materialB: '409Ti', thicknessB: 1.5, joint: 'butt', position: 'flat' },
    { length: 300, mode: 'time', time: 60, materialA: '409', thicknessA: 1.5, materialB: '409', thicknessB: 1.5, joint: 'lap', position: 'rotating' }
  ],
  vehicle: '시험 차종 A', productName: '리어 머플러',
  process: 'GMAW', equipment: '예시 로봇 용접기', gas: 'Ar98O2_2',
  batch: 2, nonArc: 30, uptime: 80, hours: 8, days: 22, months: 12
};

function setRowMode(row) {
  const directTime = row.querySelector('.row-mode').value === 'time';
  row.querySelector('.speed-wrap').hidden = directTime;
  row.querySelector('.time-wrap').hidden = !directTime;
}

function refreshRowLabels() {
  const rows = [...rowsContainer.querySelectorAll('.weld-row')];
  rows.forEach((row, index) => {
    row.querySelector('.row-title').textContent = `용접 구간 ${index + 1}`;
    row.querySelector('.remove-row').disabled = rows.length === 1;
  });
}

function addRow(data = {}) {
  const row = document.getElementById('weld-row-template').content.firstElementChild.cloneNode(true);
  row.querySelector('.row-length').value = data.length == null ? '' : String(data.length);
  row.querySelector('.row-mode').value = data.mode || 'speed';
  row.querySelector('.row-speed').value = data.speed == null ? '' : String(data.speed);
  row.querySelector('.row-time').value = data.time == null ? '' : String(data.time);
  for (const [field, selector] of Object.entries({ materialA: '.row-material-a', thicknessA: '.row-thickness-a', materialB: '.row-material-b', thicknessB: '.row-thickness-b', joint: '.row-joint', position: '.row-position' })) {
    row.querySelector(selector).value = data[field] == null ? '' : String(data[field]);
  }
  setRowMode(row);
  rowsContainer.append(row);
  refreshRowLabels();
}

function positiveNumber(raw, label) {
  if (raw.trim() === '') throw new Error(`${label}을(를) 입력해 주세요.`);
  const value = Number(raw);
  if (!Number.isFinite(value) || value <= 0) throw new Error(`${label}은(는) 0보다 커야 합니다.`);
  return value;
}

function nonnegativeNumber(raw, label) {
  if (raw.trim() === '') throw new Error(`${label}을(를) 입력해 주세요.`);
  const value = Number(raw);
  if (!Number.isFinite(value) || value < 0) throw new Error(`${label}은(는) 0 이상이어야 합니다.`);
  return value;
}

function optionalPositiveNumber(raw, label) {
  if (raw.trim() === '') return null;
  return positiveNumber(raw, label);
}

function normalizePlan(raw) {
  const rows = raw.rows.map((row, index) => {
    const label = `${index + 1}번 구간`;
    const length = positiveNumber(String(row.length), `${label} 용접 길이`);
    const mode = row.mode;
    let values;
    if (mode === 'speed') {
      const speed = positiveNumber(String(row.speed), `${label} 이동 속도`);
      values = { length, mode, speed, time: length / speed * 60 };
    } else {
      if (mode !== 'time') throw new Error(`${label}의 시간 입력 방식은 speed 또는 time이어야 합니다.`);
      const time = positiveNumber(String(row.time), `${label} 용접 시간`);
      values = { length, mode: 'time', time };
    }
    return { ...values,
      materialA: String(row.materialA || ''),
      thicknessA: optionalPositiveNumber(String(row.thicknessA || ''), `${label} 부품 A 두께`),
      materialB: String(row.materialB || ''),
      thicknessB: optionalPositiveNumber(String(row.thicknessB || ''), `${label} 부품 B 두께`),
      joint: String(row.joint || ''), position: String(row.position || '')
    };
  });
  if (rows.length === 0) throw new Error('용접 구간을 한 개 이상 추가해 주세요.');
  const input = name => String(raw[name]);
  const batch = positiveNumber(input('batch'), '한 사이클 생산 수량');
  if (!Number.isInteger(batch)) throw new Error('한 사이클 생산 수량은 정수로 입력해 주세요.');
  const nonArc = nonnegativeNumber(input('nonArc'), '비아크 시간');
  const uptime = nonnegativeNumber(input('uptime'), '가동률');
  if (uptime > 100) throw new Error('가동률은 0~100%로 입력해 주세요.');
  const hours = positiveNumber(input('hours'), '일일 근무시간');
  const days = positiveNumber(input('days'), '월간 가동일수');
  const months = positiveNumber(input('months'), '연간 가동 개월 수');
  if (!Number.isInteger(days) || days > 31) throw new Error('월간 가동일수는 1~31일의 정수로 입력해 주세요.');
  if (!Number.isInteger(months) || months > 12) throw new Error('연간 가동 개월 수는 1~12개월의 정수로 입력해 주세요.');
  return { rows, batch, nonArc, uptime, hours, days, months,
    vehicle: String(raw.vehicle || '').trim(), productName: String(raw.productName || '').trim(),
    process: String(raw.process || ''), equipment: String(raw.equipment || ''), gas: String(raw.gas || '') };
}

function readInputs() {
  const rows = [...rowsContainer.querySelectorAll('.weld-row')].map(row => ({
    length: row.querySelector('.row-length').value,
    mode: row.querySelector('.row-mode').value,
    speed: row.querySelector('.row-speed').value,
    time: row.querySelector('.row-time').value,
    materialA: row.querySelector('.row-material-a').value,
    thicknessA: row.querySelector('.row-thickness-a').value,
    materialB: row.querySelector('.row-material-b').value,
    thicknessB: row.querySelector('.row-thickness-b').value,
    joint: row.querySelector('.row-joint').value,
    position: row.querySelector('.row-position').value
  }));
  const input = name => form.elements.namedItem(name).value;
  return normalizePlan({ rows, ...Object.fromEntries(['batch', 'nonArc', 'uptime', 'hours', 'days', 'months', 'vehicle', 'productName', 'process', 'equipment', 'gas'].map(name => [name, input(name)])) });
}

function calculate(v) {
  const arc = v.rows.reduce((total, row) => total + row.time, 0);
  const cycle = arc + v.nonArc;
  const uph = 3600 / cycle * v.batch * v.uptime / 100;
  const day = uph * v.hours;
  const month = day * v.days;
  const year = month * v.months;
  return { arc, cycle, uph, day, month, year };
}

function render(v, c) {
  const fmt = x => formatter.format(x);
  document.getElementById('arc-time').textContent = fmt(c.arc);
  document.getElementById('cycle-time').textContent = fmt(c.cycle);
  document.getElementById('uph').textContent = fmt(c.uph);
  document.getElementById('daily').textContent = fmt(Math.floor(c.day));
  document.getElementById('monthly').textContent = fmt(Math.floor(c.month));
  document.getElementById('yearly').textContent = fmt(Math.floor(c.year));
  const isSample = source === 'sample' || source === 'sample-file';
  document.getElementById('source').textContent = source === 'sample' ? '예시 데이터로 계산'
    : source === 'sample-file' ? `예시 CSV 파일로 계산: ${importedName}`
    : source === 'file' ? `첨부한 CSV 파일로 계산: ${importedName}` : '사용자 입력으로 계산';
  document.getElementById('product-context').textContent = `차종: ${v.vehicle || '미입력'} · 제품명: ${v.productName || '미입력'}`;
  document.getElementById('sample-warning').hidden = !isSample;

  const lines = v.rows.map((row, index) => row.mode === 'speed'
    ? `${index + 1}번 구간: ${fmt(row.length)} mm ÷ ${fmt(row.speed)} mm/min × 60 = ${fmt(row.time)} 초`
    : `${index + 1}번 구간: ${fmt(row.length)} mm, 직접 입력한 용접 시간 ${fmt(row.time)} 초`);
  lines.push(
    `총 용접 시간: 구간별 용접 시간 합계 = ${fmt(c.arc)} 초/사이클`,
    `사이클 시간: ${fmt(c.arc)} + 비아크 시간 ${fmt(v.nonArc)} = ${fmt(c.cycle)} 초`,
    `UPH: 3,600 ÷ ${fmt(c.cycle)} × ${fmt(v.batch)}개/사이클 × ${fmt(v.uptime)}% = ${fmt(c.uph)} 개/시간`,
    `일 생산량: 반올림 전 UPH × ${fmt(v.hours)}시간 = ${fmt(Math.floor(c.day))} 개`,
    `월 생산량: 반올림 전 일 생산량 × ${fmt(v.days)}일 = ${fmt(Math.floor(c.month))} 개`,
    `년 생산량: 반올림 전 월 생산량 × ${fmt(v.months)}개월 = ${fmt(Math.floor(c.year))} 개`
  );
  document.getElementById('breakdown').replaceChildren(...lines.map(line => {
    const p = document.createElement('p');
    p.textContent = line;
    return p;
  }));
  rowsContainer.querySelectorAll('.weld-row').forEach((row, index) => {
    row.querySelector('.row-preview').textContent = `구간 용접 시간: ${fmt(v.rows[index].time)}초`;
  });
  renderWireResults(v);
  result.hidden = false;
}

function renderWireResults(v) {
  const container = document.getElementById('wire-results');
  const cards = v.rows.map((row, index) => {
    const recommendation = WeldWire.recommendWire(row, v.process, v.equipment, v.gas);
    const card = document.createElement('article');
    card.className = 'wire-card';
    const title = document.createElement('h4');
    title.textContent = `${index + 1}번 용접 구간`;
    card.append(title);
    const tag = document.createElement('span');
    tag.className = 'tag';
    tag.textContent = recommendation.status === 'candidate' ? '제조사 자료 기반 시험 후보' : '자료 부족';
    card.append(tag);
    const description = document.createElement('p');
    description.textContent = recommendation.status === 'candidate'
      ? `와이어 후보: ${recommendation.wire} — ${recommendation.reason}` : recommendation.message;
    card.append(description);
    if (recommendation.status === 'candidate') {
      const gas = document.createElement('p');
      gas.textContent = recommendation.gasNote;
      card.append(gas);
      const link = document.createElement('a');
      link.href = recommendation.sourceUrl;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.textContent = recommendation.sourceLabel;
      card.append(link);
    }
    const conditions = document.createElement('p');
    conditions.className = 'muted';
    conditions.textContent = '전압·전류·와이어 송급 속도: 사내 승인 조건 자료 없음. 시편 시험과 품질 검증 후 설정 필요.';
    card.append(conditions);
    return card;
  });
  container.replaceChildren(...cards);
}

function update() {
  try {
    const values = readInputs();
    render(values, calculate(values));
    error.hidden = true;
    hasCalculated = true;
  } catch (ex) {
    error.textContent = ex.message;
    error.hidden = false;
    result.hidden = true;
  }
}

function changed() {
  source = 'user';
  importedName = '';
  if (hasCalculated) update();
}

function applyPlan(plan) {
  rowsContainer.replaceChildren();
  plan.rows.forEach(addRow);
  for (const name of ['batch', 'nonArc', 'uptime', 'hours', 'days', 'months', 'vehicle', 'productName', 'process', 'equipment', 'gas']) {
    form.elements.namedItem(name).value = String(plan[name]);
  }
}

form.addEventListener('submit', event => { event.preventDefault(); update(); });
form.addEventListener('input', changed);
form.addEventListener('change', event => {
  const row = event.target.closest('.weld-row');
  if (row && event.target.classList.contains('row-mode')) setRowMode(row);
  changed();
});
rowsContainer.addEventListener('click', event => {
  if (!event.target.classList.contains('remove-row')) return;
  event.target.closest('.weld-row').remove();
  refreshRowLabels();
  changed();
});
addButton.addEventListener('click', () => { addRow(); changed(); });
sampleButton.addEventListener('click', () => {
  applyPlan(example);
  source = 'sample';
  importedName = '';
  update();
});
fileInput.addEventListener('change', async () => {
  const file = fileInput.files[0];
  if (!file) return;
  try {
    if (!file.name.toLowerCase().endsWith('.csv')) throw new Error('CSV 파일만 첨부할 수 있습니다.');
    if (file.size > 1024 * 1024) throw new Error('CSV 파일은 1MB 이하로 첨부해 주세요.');
    const plan = WeldCsv.parsePlanCsv(await file.text());
    normalizePlan(plan); // 입력 화면을 바꾸기 전에 파일 전체를 검증한다.
    applyPlan(plan);
    importedName = file.name;
    source = plan.sample ? 'sample-file' : 'file';
    fileStatus.textContent = `${file.name} 파일의 용접 구간 ${plan.rows.length}개를 불러왔습니다.`;
    update();
  } catch (ex) {
    fileStatus.textContent = `${file.name} 파일을 불러오지 못했습니다.`;
    error.textContent = ex.message;
    error.hidden = false;
  } finally {
    fileInput.value = '';
  }
});
addRow();
