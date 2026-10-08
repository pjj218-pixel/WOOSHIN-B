const assert = require('node:assert/strict');
const { recommendWire } = require('./wire-rules.js');
const row = (materialA, materialB) => ({ materialA, materialB, thicknessA: 1.5, thicknessB: 1.5, joint: 'butt', position: 'flat' });

assert.equal(recommendWire(row('409', '409Ti'), 'GMAW', '로봇 1호기', 'Ar98O2_2').wire, 'ER409Nb');
assert.equal(recommendWire(row('304L', '304L'), 'GMAW', '로봇 1호기', 'Ar98CO2_2').wire, 'ER308L 또는 ER308LSi');
assert.equal(recommendWire(row('carbon', '304L'), 'GMAW', '로봇 1호기', 'Ar98CO2_2').wire, 'ER309LSi');
assert.match(recommendWire(row('409', '409'), 'GMAW', '로봇 1호기', 'Ar98CO2_2').gasNote, /다릅니다/);
assert.equal(recommendWire(row('409', '409'), 'GTAW', '로봇 1호기', 'Ar98O2_2').status, 'insufficient');
assert.equal(recommendWire(row('409', '304L'), 'GMAW', '로봇 1호기', 'Ar98O2_2').status, 'insufficient');
assert.equal(recommendWire({ ...row('409', '409'), thicknessA: null }, 'GMAW', '로봇 1호기', 'Ar98O2_2').status, 'insufficient');
console.log('와이어 후보 검증 통과: 409, 304L, 탄소강/304L, 가스 불일치, 미지원 조합');
