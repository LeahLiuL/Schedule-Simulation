/* Round-trip test for the transposed cul_ship_particular.csv writer.
 * Extracts the REAL parseCSV / particularToCSV / appendParticularColumn
 * source out of shipping_schedule.html and runs it in a vm sandbox. */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = 'c:/Users/leahliu/WorkBuddy/20260325092900';
const html = fs.readFileSync(path.join(ROOT, 'shipping_schedule.html'), 'utf8').replace(/\r\n/g, '\n');

function slice(startMarker, endMarker) {
  const i = html.indexOf(startMarker);
  if (i < 0) throw new Error('start marker not found: ' + startMarker);
  const j = html.indexOf(endMarker, i);
  if (j < 0) throw new Error('end marker not found: ' + endMarker);
  return html.slice(i, j);
}

const parseCSVSrc = slice('function parseCSV(text){', '\n// Fetch CSV:');
const csvWriteSrc = slice('function csvCell(v){', '\n// Generic GitHub Contents API PUT');

const sandbox = { PARTICULAR_DATA: [], window: {} };
vm.createContext(sandbox);
vm.runInContext(parseCSVSrc + '\n' + csvWriteSrc +
  '\n;this.parseCSV=parseCSV;this.particularToCSV=particularToCSV;this.appendParticularColumn=appendParticularColumn;', sandbox);

const csvPath = path.join(ROOT, 'shipping_data/cul_ship_particular.csv');
const raw = fs.readFileSync(csvPath, 'utf8').replace(/^\uFEFF/, '');

sandbox.PARTICULAR_DATA = sandbox.parseCSV(raw);
sandbox.window._particularVessels = Object.keys(sandbox.PARTICULAR_DATA[0]).slice(1);

let fail = 0;
function ok(name, cond, extra) {
  console.log(`  ${cond ? 'PASS' : 'FAIL'}  ${name}${extra ? '  ' + extra : ''}`);
  if (!cond) fail++;
}

console.log('=== A. round-trip WITHOUT changes ===');
const before = sandbox.particularToCSV();
const origLines = raw.replace(/\r\n/g, '\n').split('\n').filter(l => l.trim() !== '' && l.replace(/,/g, '') !== '');
const newLines = before.split('\n').filter(l => l.trim() !== '' && l.replace(/,/g, '') !== '');
ok('field row count preserved', origLines.length === newLines.length, `${origLines.length} vs ${newLines.length}`);
// Compare cell-by-cell (trimmed, trailing blanks ignored): the writer legitimately
// pads short rows to the full column count and trims stray spaces.
function cells(line) {
  const a = line.split(',').map(s => s.trim());
  while (a.length && a[a.length - 1] === '') a.pop();
  return a;
}
let diff = 0;
for (let k = 0; k < Math.min(origLines.length, newLines.length); k++) {
  const o = cells(origLines[k]), n = cells(newLines[k]);
  const w = Math.max(o.length, n.length);
  for (let c = 0; c < w; c++) {
    if ((o[c] || '') !== (n[c] || '')) {
      if (diff < 5) console.log(`    DIFF row ${k} col ${c}: ${JSON.stringify(o[c])} -> ${JSON.stringify(n[c])}`);
      diff++;
    }
  }
}
ok('every cell value preserved', diff === 0, `${diff} differing cell(s)`);

const vesselCountBefore = Object.keys(sandbox.PARTICULAR_DATA[0]).length - 1;
console.log(`  (${vesselCountBefore} vessels, ${sandbox.PARTICULAR_DATA.length} field rows)`);

console.log('\n=== B. append a new vessel column ===');
const newVessel = {
  vessel_name: 'CUL TEST STAR', call_sign: '3EXX9', imo: '9876543', flag: 'Panama',
  year_built: '2019', teu: '1800', homogeneous: '1300', grt: '18500', nrt: '9200',
  scantling_draft: '9.80', dwt: '24500', loa: '172.0', breadth: '27.6', depth: '14.2',
  reefer_plugs: '300', class: 'NK'
};
const colKey = sandbox.appendParticularColumn(newVessel);
ok('column key returned', colKey === 'CUL TEST STAR', JSON.stringify(colKey));

const after = sandbox.particularToCSV();
const aLines = after.split('\n');
const header = aLines[0].split(',');
ok('header gained exactly 1 column', header.length === vesselCountBefore + 2, `${header.length} cols`);
ok('new column is last in header', header[header.length - 1] === 'CUL TEST STAR', header[header.length - 1]);

// verify each field row got the right value in the last column
const EXPECT = {
  'CALL SIGN': '3EXX9', 'IMO': '9876543', 'FLAG': 'Panama', 'YEAR BUILT': '2019',
  'NOMINAL CAPACITY (TEU)': '1800', 'HOMO @14 MT': '1300', 'GRT': '18500', 'NRT': '9200',
  'SCANTLING DRAFT (m)': '9.80', 'DWT (MT)': '24500', 'LOA (m)': '172.0',
  'BREADTH (m)': '27.6', 'DEPTH (m)': '14.2', 'REEFER PLUGS': '300', 'CLASS': 'NK'
};
for (const [label, want] of Object.entries(EXPECT)) {
  const row = aLines.find(l => l.split(',')[0] === label);
  const got = row ? row.split(',').pop() : '<row missing>';
  ok(`${label.padEnd(24)} -> ${want}`, got === want, `got=${JSON.stringify(got)}`);
}

// existing vessels untouched
console.log('\n=== C. existing data untouched ===');
let untouched = true;
for (let k = 0; k < origLines.length; k++) {
  const oldCells = origLines[k].split(',');
  const newRow = aLines.filter(l => l.trim() !== '')[k].split(',');
  for (let c = 0; c < oldCells.length; c++) {
    if (oldCells[c].trim() !== newRow[c].trim()) {
      console.log('    CHANGED row', k, 'col', c, JSON.stringify(oldCells[c]), '->', JSON.stringify(newRow[c]));
      untouched = false;
    }
  }
}
ok('every pre-existing cell identical', untouched);

console.log('\n==========================================');
console.log(fail === 0 ? 'ALL CSV ROUND-TRIP CHECKS PASSED' : `${fail} CHECK(S) FAILED`);
process.exit(fail === 0 ? 0 : 1);
