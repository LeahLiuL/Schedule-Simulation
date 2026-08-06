// Verify the REAL exportExcel() (formula mode) extracted from shipping_schedule.html
// by running it headlessly against the real exceljs package, then inspect the
// emitted formulas to confirm the time-chain cascades correctly.
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const WS = 'C:/Users/leahliu/.workbuddy/binaries/node/workspace/node_modules';
const ExcelJSReal = require(path.join(WS, 'exceljs'));

const html = fs.readFileSync('shipping_schedule.html', 'utf8').replace(/\r\n/g, '\n');

function slice(startMark, endMark, label) {
  const a = html.indexOf(startMark);
  if (a < 0) throw new Error('start marker not found: ' + label);
  const b = html.indexOf(endMark, a);
  if (b < 0) throw new Error('end marker not found: ' + label);
  return html.slice(a, b);
}

const srcExport  = slice('// ==================== EXPORT EXCEL ====================',
                         '// ==================== TOAST ====================', 'export');
const srcColDefs = slice('const COL_DEFS = [', '];', 'COL_DEFS') + '];';
const srcFmtDt   = slice('function fmtDt(d){', '\n}\n', 'fmtDt') + '\n}';

console.log('extracted: export=' + srcExport.length + 'B, COL_DEFS=' + srcColDefs.length +
            'B, fmtDt=' + srcFmtDt.length + 'B');

let capturedWb = null;
class CapturingWorkbook extends ExcelJSReal.Workbook {
  constructor() { super(); capturedWb = this; }
}

const inputs = { vesselInput: 'CUL QINGDAO', voyNoInput: '025W', speedInput: '14.5' };
const toasts = [];
const D = (s) => new Date(s);

const scheduleRows = [
  { idx:0, port:'CNSHA', manIn:2, wait:0, proformaEta:D('2026-08-10T06:00'), proformaEtd:D('2026-08-11T06:00'),
    ltsEtb:D('2026-08-10T08:00'), ltsEtd:D('2026-08-11T06:00'), voyNo:'025W', date:D('2026-08-10T06:00'),
    eta:D('2026-08-10T06:00'), etb:D('2026-08-10T08:00'), etd:D('2026-08-11T06:00'),
    runHrs:12.5, stayHrs:22, dist:181.3, speed:14.5, etaDelay:0, etdDelay:0, fuelSea:14.32, remark:'Load', modified:false },
  { idx:1, port:'CNNGB', manIn:2, wait:1, proformaEta:D('2026-08-11T18:00'), proformaEtd:D('2026-08-12T20:00'),
    ltsEtb:D('2026-08-11T21:00'), ltsEtd:D('2026-08-12T20:00'), voyNo:'025W', date:D('2026-08-11T18:00'),
    eta:D('2026-08-11T18:00'), etb:D('2026-08-11T21:00'), etd:D('2026-08-12T20:00'),
    runHrs:152.0, stayHrs:23, dist:2204.0, speed:14.5, etaDelay:5, etdDelay:5, fuelSea:174.11, remark:'', modified:true },
  { idx:2, port:'SGSIN', manIn:3, wait:0, proformaEta:D('2026-08-18T04:00'), proformaEtd:D('2026-08-19T10:00'),
    ltsEtb:D('2026-08-18T07:00'), ltsEtd:D('2026-08-19T10:00'), voyNo:'025W', date:D('2026-08-18T04:00'),
    eta:D('2026-08-18T04:00'), etb:D('2026-08-18T07:00'), etd:D('2026-08-19T10:00'),
    runHrs:216.4, stayHrs:27, dist:3137.8, speed:14.5, etaDelay:-3, etdDelay:-3, fuelSea:247.86, remark:'Transhipment', modified:false },
  { idx:3, port:'OMDQM', manIn:2, wait:2, proformaEta:D('2026-08-27T02:00'), proformaEtd:D('2026-08-28T08:00'),
    ltsEtb:D('2026-08-27T06:00'), ltsEtd:D('2026-08-28T08:00'), voyNo:'025W', date:D('2026-08-27T02:00'),
    eta:D('2026-08-27T02:00'), etb:D('2026-08-27T06:00'), etd:D('2026-08-28T08:00'),
    runHrs:387.5, stayHrs:26, dist:5619.0, speed:14.5, etaDelay:0, etdDelay:0, fuelSea:443.79, remark:'', modified:false },
  { idx:4, port:'CNTAO', manIn:2, wait:0, proformaEta:D('2026-09-13T12:00'), proformaEtd:D('2026-09-14T14:00'),
    ltsEtb:D('2026-09-13T14:00'), ltsEtd:D('2026-09-14T14:00'), voyNo:'025W', date:D('2026-09-13T12:00'),
    eta:D('2026-09-13T12:00'), etb:D('2026-09-13T14:00'), etd:D('2026-08-14T14:00'),
    runHrs:0, stayHrs:24, dist:0, speed:14.5, etaDelay:12, etdDelay:12, fuelSea:0, remark:'Discharge', modified:false },
];

const sandbox = {
  ExcelJS: { Workbook: CapturingWorkbook },
  console,
  Date, Math, Number, String, Object, Array, JSON, parseFloat, parseInt, isNaN,
  localStorage: { getItem: () => '[]', setItem: () => {} },
  scheduleRows,
  selectedPorts: scheduleRows.map(r => ({ code: r.port })),
  currentVessel: { code: 'CUL QINGDAO', name: 'CUL QINGDAO V.025W', lsfo: 27.5 },
  DEFAULT_MAN_IN: 2,
  svHiddenCols: [],
  showToast: (m, t) => toasts.push(t + ': ' + m),
  document: {
    getElementById: (id) => id === 'xlFormulaChk' ? { checked: process.env.FORMULA !== '0' }
                        : ({ value: inputs[id] !== undefined ? inputs[id] : '' }),
    createElement: () => ({ set href(v) {}, set download(v) {}, click() {} }),
  },
  Blob: function (parts) { this.parts = parts; },
  URL: { createObjectURL: () => 'blob://x', revokeObjectURL: () => {} },
};
sandbox.window = sandbox;
vm.createContext(sandbox);

vm.runInContext(srcColDefs, sandbox, { filename: 'COL_DEFS.js' });
vm.runInContext(srcFmtDt, sandbox, { filename: 'fmtDt.js' });
vm.runInContext(
  'function isSVColHidden(k){return svHiddenCols.indexOf(k)>=0;}\n' +
  'function getVisibleSVCols(){return COL_DEFS.filter(c=>!c.hideable||!isSVColHidden(c.key));}',
  sandbox, { filename: 'colvis.js' });
vm.runInContext(srcExport, sandbox, { filename: 'exportExcel.js' });

vm.runInContext('exportExcel();', sandbox, { filename: 'run.js' });

setTimeout(() => {
  if (!capturedWb) { console.log('FAIL: workbook never created'); process.exit(1); }
  console.log('toasts:', toasts);
  const ws = capturedWb.getWorksheet('Voyage Schedule');
  console.log('sheets:', capturedWb.worksheets.map(w => w.name).join(', '));
  // Print header + formula cells for rows 4..8
  const header = [];
  ws.getRow(4).eachCell((c, col) => header[col] = c.value);
  console.log('HEADER:', header.slice(1).map((h,i)=> (i+1)+'='+h).join(' | '));
  let formulaCount = 0;
  for (let r = 5; r <= 9; r++) {
    const out = [];
    ws.getRow(r).eachCell((c, col) => {
      const f = c.formula ? c.formula : (c.value && c.value.formula ? c.value.formula : null);
      if (f) { formulaCount++; out.push((col) + ':' + f); }
    });
    console.log('ROW' + r + ' formulas => ' + out.join('  '));
  }
  // Summary live formulas
  const ws2 = capturedWb.getWorksheet('Summary');
  const sums = [];
  ws2.eachRow((row, rn) => {
    const c2 = row.getCell(2);
    const f = c2.value && c2.value.formula ? c2.value.formula : null;
    if (f) sums.push(row.getCell(1).value + ' => ' + f);
  });
  console.log('SUMMARY formulas:');
  sums.forEach(s => console.log('  ' + s));
  console.log('TOTAL formula cells in schedule:', formulaCount);

  const out = 'test_export_formula.xlsx';
  capturedWb.xlsx.writeFile(out).then(() => {
    console.log('WROTE ' + out + ' (' + fs.statSync(out).size + ' bytes)');
  }).catch(e => { console.log('WRITE FAIL:', e.message); process.exit(1); });
}, 300);
