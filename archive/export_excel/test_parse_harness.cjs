/* Extracts the REAL parser source out of shipping_schedule.html and runs it
 * in a vm sandbox against sample TCD text. No mocks of the parser itself. */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = 'c:/Users/leahliu/WorkBuddy/20260325092900';
const html = fs.readFileSync(path.join(ROOT, 'shipping_schedule.html'), 'utf8').replace(/\r\n/g, '\n');

const START = '// Client-side parse function\n';
const END = '\nfunction displayParseResult(result){';
const i = html.indexOf(START);
const j = html.indexOf(END, i);
if (i < 0 || j < 0) { console.error('markers not found'); process.exit(1); }
const code = html.slice(i, j);
console.log('extracted %d chars / %d lines of real parser source\n', code.length, code.split('\n').length);

const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(code + '\n;this.parseVesselTextClient = parseVesselTextClient; this.buildFuelTiers = buildFuelTiers;', sandbox);

// ---------------- expectations ----------------
function check(name, got, want) {
  const ok = String(got == null ? '' : got) === String(want == null ? '' : want);
  console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${name.padEnd(22)} got=${JSON.stringify(got)} want=${JSON.stringify(want)}`);
  return ok;
}

let total = 0, pass = 0;
function run(title, text, expect) {
  console.log('=== ' + title + ' ===');
  const r = sandbox.parseVesselTextClient(text);
  console.log('  particular:', JSON.stringify(r.particular));
  console.log('  fuel      :', JSON.stringify(r.fuel));
  console.log('  debug     :', JSON.stringify(r.debug));
  console.log('  fuelType  :', r.fuelType);
  console.log('  --- assertions ---');
  for (const [k, v] of Object.entries(expect.particular || {})) {
    total++; if (check(k, r.particular[k], v)) pass++;
  }
  (expect.fuel || []).forEach((f, idx) => {
    const g = r.fuel[idx] || {};
    for (const [k, v] of Object.entries(f)) {
      total++; if (check(`fuel[${idx}].${k}`, g[k], v)) pass++;
    }
  });
  if (expect.fuelType) { total++; if (check('fuelType', r.fuelType, expect.fuelType)) pass++; }
  console.log('  warnings  :', JSON.stringify(r.warnings));
  console.log('');
  return r;
}

// ---------------- Case 1: real TCD (V1500TEU, docx text) ----------------
const s1 = fs.readFileSync(path.join(ROOT, 'tcd_samples/sample_v1500.txt'), 'utf8');
run('Case 1 — real TCD  M.V1500TEU (IV)', s1, {
  particular: {
    flag: 'Panama', class: 'ICS', year_built: '2026',
    grt: '16925', nrt: '9478', loa: '156.3', breadth: '27.3', depth: '13.8',
    dwt: '27606', scantling_draft: '10.1', teu: '1510', homogeneous: '1230',
    reefer_plugs: '50'
  },
  fuel: [
    { speed: '13', lsfo: '20', hsfo: '', mgo: '', port_lsfo: '0.8', port_mgo: '1.2' },
    { speed: '12', lsfo: '18', port_lsfo: '0.8', port_mgo: '1.2' },
    { speed: '11', lsfo: '16', port_lsfo: '0.8', port_mgo: '1.2' }
  ],
  fuelType: 'LSFO'
});

// ---------------- Case 2: the placeholder format in the textarea ----------------
const s2 = `Vessel Name: CUL TEST STAR
Call Sign: 3EXX9
IMO: 9876543
Flag: Panama
Year Built: 2019
Class: NK
Nominal capacity: 1800 TEU
Homogeneous capacity: 1300 TEU
GRT: 18500
NRT: 9200
DWT: 24500 MT
Scantling draft: 9.80 m
LOA: 172.0 m
Breadth: 27.6 m
Depth: 14.2 m
Reefer plugs: 300

Speed and consumption:
17.0 knots on 45.5 MT HSFO
15.0 knots on 33.0 MT HSFO
13.0 knots on 24.0 MT HSFO
Auxiliary consumption at sea: 2.5 MT HSFO
In port working: 4.0 MT MGO
`;
run('Case 2 — clean key:value + HSFO', s2, {
  particular: {
    vessel_name: 'CUL TEST STAR', call_sign: '3EXX9', imo: '9876543', flag: 'Panama',
    year_built: '2019', class: 'NK', teu: '1800', homogeneous: '1300',
    grt: '18500', nrt: '9200', dwt: '24500', scantling_draft: '9.80',
    loa: '172.0', breadth: '27.6', depth: '14.2', reefer_plugs: '300'
  },
  fuel: [
    { speed: '17', hsfo: '48', mgo: '', port_mgo: '4' },
    { speed: '15', hsfo: '35.5' },
    { speed: '13', hsfo: '26.5' }
  ],
  fuelType: 'HSFO'
});

// ---------------- Case 3: junk / unrelated text ----------------
const r3 = sandbox.parseVesselTextClient('Hello world, nothing here.');
console.log('=== Case 3 — junk input ===');
total++; if (check('success', r3.success, false)) pass++;
console.log('  warnings:', JSON.stringify(r3.warnings), '\n');

console.log('==========================================');
console.log(`RESULT: ${pass}/${total} assertions passed`);
process.exit(pass === total ? 0 : 1);
