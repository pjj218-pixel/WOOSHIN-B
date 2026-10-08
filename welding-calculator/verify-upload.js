const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const { parsePlanCsv } = require('./csv-import.js');
const { recommendWire } = require('./wire-rules.js');

function node() {
  return { value: '', textContent: '', hidden: false, disabled: false, handlers: {},
    addEventListener(type, handler) { this.handlers[type] = handler; },
    replaceChildren(...children) { this.children = children; },
    append(...children) { this.children = [...(this.children || []), ...children]; } };
}
function weldRow() {
  const cells = Object.fromEntries(['.row-length', '.row-mode', '.row-speed', '.row-time', '.speed-wrap', '.time-wrap', '.row-title', '.remove-row', '.row-preview', '.row-material-a', '.row-thickness-a', '.row-material-b', '.row-thickness-b', '.row-joint', '.row-position'].map(key => [key, node()]));
  return { querySelector: key => cells[key], cloneNode: weldRow, remove() {} };
}
const dom = new Map();
function get(id) { if (!dom.has(id)) dom.set(id, node()); return dom.get(id); }
const rows = [];
const container = get('weld-rows');
container.querySelectorAll = () => rows;
container.append = row => rows.push(row);
container.replaceChildren = () => { rows.length = 0; };
const form = get('calculator');
const fields = Object.fromEntries(['batch', 'nonArc', 'uptime', 'hours', 'days', 'months', 'vehicle', 'productName', 'process', 'equipment', 'gas'].map(key => [key, node()]));
form.elements = { namedItem: key => fields[key] };
const fileInput = get('csv-file');
const template = get('weld-row-template');
template.content = { firstElementChild: { cloneNode: weldRow } };
const document = { getElementById: get, createElement: node };
const context = vm.createContext({ document, Intl, Number, Object, Error, Math, String, WeldCsv: { parsePlanCsv }, WeldWire: { recommendWire } });
vm.runInContext(fs.readFileSync('app.js', 'utf8'), context);

(async () => {
  const sample = fs.readFileSync('예시_용접조건.csv', 'utf8');
  fileInput.files = [{ name: '예시_용접조건.csv', size: Buffer.byteLength(sample), text: async () => sample }];
  await fileInput.handlers.change();
  assert.equal(rows.length, 2);
  assert.equal(fields.batch.value, '2');
  assert.equal(fields.vehicle.value, '시험 차종 A');
  assert.equal(fields.productName.value, '리어 머플러');
  assert.equal(get('arc-time').textContent, '180');
  assert.equal(get('yearly').textContent, '57,929');
  assert.match(get('source').textContent, /예시 CSV 파일로 계산/);
  assert.equal(get('sample-warning').hidden, false);
  assert.equal(get('error').hidden, true);
  assert.match(get('product-context').textContent, /시험 차종 A · 제품명: 리어 머플러/);
  assert.equal(get('wire-results').children.length, 2);
  assert.match(get('wire-results').children[0].children[2].textContent, /ER409Nb/);

  fileInput.files = [{ name: '오류.csv', size: 20, text: async () => 'wrong,columns\n1,2' }];
  await fileInput.handlers.change();
  assert.equal(rows.length, 2, '오류 파일은 기존 입력을 바꾸지 않아야 합니다.');
  assert.equal(get('error').hidden, false);
  console.log('파일 첨부 이벤트 검증 통과: 예시 CSV → 입력 반영 → 계산 결과 표시');
  console.log('오류 CSV 검증 통과: 기존 입력 보존 및 오류 안내');
})().catch(error => { console.error(error); process.exitCode = 1; });
