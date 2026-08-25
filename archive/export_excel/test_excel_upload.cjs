/* Excel-upload pipeline test: slices the REAL parseExcelContent + parseVesselTextClient
 * out of shipping_schedule.html, feeds a TCD-style xlsx built with the real
 * SheetJS package (same 0.18.5 as the page), and asserts the converted text
 * and parsed result. */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..', '..');
const WS = 'C:/Users/leahliu/.workbuddy/binaries/node/workspace/node_modules';
const XLSX = require(path.join(WS, 'xlsx'));

const html = fs.readFileSync(path.join(ROOT, 'shipping_schedule.html'), 'utf8').replace(/\r\n/g, '\n');

function slice(startMark, endMark, label) {
  const a = html.indexOf(startMark);
  if (a < 0) throw new Error('start marker not found: ' + label);
  const b = html.indexOf(endMark, a);
  if (b < 0) throw new Error('end marker not found: ' + label);
  return html.slice(a, b);
}

const srcExcel  = slice('// Excel TCD: SheetJS', '\nfunction parseVesselText(){', 'parseExcelContent');
const srcParser = slice('// Client-side parse function\n', '\nfunction displayParseResult(result){', 'parser');
console.log('extracted: parseExcelContent=%dB, parser=%dB', srcExcel.length, srcParser.length);

let capturedText = null;
const toasts = [];
const sandbox = {
  XLSX, console, Math, JSON, Object, Array, String, Number, parseFloat, parseInt, isNaN,
  showToast: (m, t) => toasts.push((t || '') + ': ' + m),
  document: {
    getElementById: (id) => {
      if (id === 'parseVesselInput') {
        return { get value(){ return capturedText || ''; }, set value(v){ capturedText = v; } };
      }
      return { value: '', style: {}, classList: { add(){}, remove(){} }, innerHTML: '', textContent: '' };
    }
  }
};
vm.createContext(sandbox);
vm.runInContext(
  srcExcel + '\n' + srcParser + '\n' +
  'this.parseExcelContent = parseExcelContent;\n' +
  'this.parseVesselTextClient = parseVesselTextClient;',
  sandbox);

// ---- build a TCD-like workbook (2 sheets, thousands separators, fuel table) ----
const aoa = [
  ['VESSEL', 'KOTA EXPRESS', '', ''],
  ['IMO', '9123456', 'CALL SIGN', 'ABCDEF'],
  ['FLAG', 'PANAMA', 'YEAR BUILT', '2015'],
  ['NOMINAL CAPACITY (TEU)', '1,100', 'REEFER PLUGS', '120'],
  ['DEADWEIGHT (MT)', '13,500.8', 'LOA (M)', '156.3'],
  [],
  ['Fuel Consumption'],
  ['Ship Speed', 'FOC (MT)', 'Rpm'],
  ['13', '22.4', '105'],
  ['12', '18.2', '99'],
  ['Auxiliary Consumption'],
  ['At Sea: About 1.2 mt IFO 180 CST'],
];
const wb = XLSX.utils.book_new();
XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(aoa), 'Particulars');
XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet([['GROSS TONNAGE', '9,478'], ['NRT', '5200']]), 'Misc');
const buf = XLSX.write(wb, { type: 'buffer', bookType: 'xlsx' });
const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);

// ---- run the REAL parseExcelContent, intercepting parseVesselText via stub ----
sandbox.parseVesselText = () => { /* replaced below: keep name alive */ };
vm.runInContext(
  'var _realExcel = this.parseExcelContent;\n' +
  'this.parseExcelContent = function(){ return _realExcel.apply(null, arguments); };',
  sandbox);
// call parseExcelContent but temporarily swap parseVesselText to capture + parse
let parseResult = null;
const capturedFnBackup = sandbox.parseVesselText;
vm.runInContext(
  'this.parseVesselText = function(){ var t = document.getElementById("parseVesselInput").value.trim();' +
  ' if(!t){ return; } this.__last = this.parseVesselTextClient(t); };',
  sandbox);
sandbox.parseExcelContent(ab, 'kota.xlsx');
parseResult = sandbox.__last;

if (!capturedText) { console.error('FAIL: no text captured | toasts:', JSON.stringify(toasts)); process.exit(1); }
console.log('---- converted text ----');
console.log(capturedText);
console.log('---- parse result (particular) ----');
console.log(JSON.stringify(parseResult.particular));
console.log('fuel tiers:', JSON.stringify(parseResult.fuel));
console.log('fuelType:', parseResult.fuelType, '| warnings:', JSON.stringify(parseResult.warnings));

const assert = require('assert');
assert.match(capturedText, /13500\.8/, 'thousands-comma stripped (DWT)');
assert.match(capturedText, /9478/, '2nd sheet merged (GRT)');
assert.match(capturedText, /^13 22\.4 105$/m, 'fuel row space-joined');
assert.match(capturedText, /^VESSEL KOTA EXPRESS$/m, 'label+value joined');
assert.ok(parseResult.fuel.length >= 2, 'fuel tiers parsed');
console.log('\nALL ASSERTIONS PASSED  |  toasts:', JSON.stringify(toasts));
