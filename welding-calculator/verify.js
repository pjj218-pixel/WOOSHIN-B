const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const { parsePlanCsv } = require('./csv-import.js');

const source = fs.readFileSync('app.js', 'utf8');
const start = source.indexOf('function positiveNumber(');
const end = source.indexOf('function render(', start);
assert.ok(start >= 0 && end > start, '검증할 계산 함수를 찾을 수 없습니다.');

let rows = [];
const values = { batch: '2', nonArc: '30', uptime: '80', hours: '8', days: '22', months: '12' };
const row = (length, mode, speed = '', time = '') => ({
  querySelector(selector) {
    const fields = { '.row-length': length, '.row-mode': mode, '.row-speed': speed, '.row-time': time };
    return { value: fields[selector] == null ? '' : String(fields[selector]) };
  }
});
const context = vm.createContext({
  rowsContainer: { querySelectorAll: () => rows },
  form: { elements: { namedItem: name => ({ value: values[name] }) } },
  Number, Math, Error
});
vm.runInContext(source.slice(start, end), context);

const attachedExample = parsePlanCsv(fs.readFileSync('예시_용접조건.csv', 'utf8'));
assert.equal(attachedExample.sample, true);
assert.equal(attachedExample.rows.length, 2);
const imported = vm.runInContext('calculate(normalizePlan(plan))', vm.createContext({ plan: attachedExample, Number, Math, Error, ...Object.fromEntries(['positiveNumber', 'nonnegativeNumber', 'normalizePlan', 'calculate'].map(name => [name, vm.runInContext(name, context)])) }));
assert.equal(imported.arc, 180);
assert.equal(imported.cycle, 210);
assert.equal(Math.floor(imported.year), 57929);

rows = [row(600, 'speed', 300), row(300, 'time', '', 60)];
let result = vm.runInContext('calculate(readInputs())', context);
assert.equal(result.arc, 180);
assert.equal(result.cycle, 210);
assert.ok(Math.abs(result.uph - 27.42857142857143) < 1e-9);
assert.equal(Math.floor(result.day), 219);
assert.equal(Math.floor(result.month), 4827);
assert.equal(Math.floor(result.year), 57929);

rows = [row(600, 'speed', 300)];
values.batch = '1';
result = vm.runInContext('calculate(readInputs())', context);
assert.equal(result.arc, 120);
assert.equal(result.cycle, 150);
assert.equal(result.uph, 19.2);

rows = [row(600, 'speed', 0)];
assert.throws(() => vm.runInContext('readInputs()', context), /이동 속도/);
rows = [row(600, 'time', '', 0)];
assert.throws(() => vm.runInContext('readInputs()', context), /용접 시간/);
rows = [row(600, 'speed', 300)];
values.batch = '1.5';
assert.throws(() => vm.runInContext('readInputs()', context), /정수/);
values.batch = '2';
values.uptime = '0';
assert.equal(vm.runInContext('calculate(readInputs()).uph', context), 0);

console.log('복수 구간·2개/사이클 검증: 용접 180초, 사이클 210초, 일 219개, 월 4,827개, 년 57,929개');
console.log('단일 구간 기존 계산 검증: 아크 120초, 사이클 150초, UPH 19.2');
console.log('입력 검증: 속도·직접 입력 시간 0 거부, 수량 정수 제한, 가동률 0% 허용');
console.log('실제 예시 CSV 파일 읽기·검증·계산 통과');
