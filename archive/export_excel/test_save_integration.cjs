/* End-to-end integration test: real parseVesselTextClient -> displayParseResult
 * -> saveParseVessel (no-token path) against a real TCD sample, with a mocked
 * DOM. Asserts the generated vessels.csv + cul_ship_particular.csv strings are
 * correct. No mocks of the parser / CSV builder itself. */

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = 'c:/Users/leahliu/WorkBuddy/20260325092900';
const html = fs.readFileSync(path.join(ROOT, 'shipping_schedule.html'), 'utf8').replace(/\r\n/g, '\n');

// ---- brace-matching extraction helpers ----
function extractFn(src, name) {
  const sigs = ['async function ' + name + '(', 'function ' + name + '('];
  let idx = -1;
  for (const s of sigs) { const i = src.indexOf(s); if (i >= 0) { idx = i; break; } }
  if (idx < 0) throw new Error('function not found: ' + name);
  let b = src.indexOf('{', idx), depth = 0, i = b;
  for (; i < src.length; i++) {
    const c = src[i];
    if (c === '{') depth++;
    else if (c === '}') { depth--; if (depth === 0) { i++; break; } }
  }
  return src.slice(idx, i);
}
function extractVarObj(src, name) {
  const sig = 'var ' + name + ' = {';
  const si = src.indexOf(sig);
  if (si < 0) throw new Error('obj not found: ' + name);
  let b = src.indexOf('{', si), depth = 0, i = b;
  for (; i < src.length; i++) {
    const c = src[i];
    if (c === '{') depth++;
    else if (c === '}') { depth--; if (depth === 0) { i++; break; } }
  }
  return src.slice(si, i) + ';';
}

// real parser slice (parseVesselTextClient + buildFuelTiers + their deps)
const START = '// Client-side parse function\n';
const END = '\nfunction displayParseResult(result){';
const si = html.indexOf(START), ej = html.indexOf(END, si);
if (si < 0 || ej < 0) { console.error('parser markers not found'); process.exit(1); }
const parseSlice = html.slice(si, ej);

const code = [
  extractFn(html, 'parseCSV'),
  extractFn(html, 'csvCell'),
  extractVarObj(html, 'PARTICULAR_LABEL_TO_KEY'),
  extractFn(html, 'particularHeaderKeys'),
  extractFn(html, 'particularHeaderName'),
  extractFn(html, 'particularToCSV'),
  extractFn(html, 'appendParticularColumn'),
  extractFn(html, 'buildCSV'),
  extractFn(html, 'displayParseResult'),
  extractFn(html, 'addParseFuelRow'),
  extractFn(html, 'onFuelTypeChange'),
  extractFn(html, 'saveParseVessel'),
  parseSlice,
].join('\n');

// ---- fake DOM ----
function FakeEl(id) { this.id = id; this.value = ''; this.style = {}; this._children = []; this._inputs = []; this._isLabel = false; this._html = ''; }
FakeEl.prototype.appendChild = function (c) { this._children.push(c); return c; };
FakeEl.prototype.remove = function () {};
FakeEl.prototype.querySelectorAll = function (sel) { return sel === 'input' ? this._inputs : []; };
Object.defineProperty(FakeEl.prototype, 'innerHTML', { set(v) { if (v === '') this._children = []; this._html = v; }, get() { return this._html; } });
Object.defineProperty(FakeEl.prototype, 'children', { get() { return this._children; } });

const els = {};
const NEEDED = ['parseVesselResult','parseWarnBox','parsePreviewBox','parseFuelRows','parseParticularStatus','parseFuelStatus','pv_fuel_type','pv_vessel_code','pv_vessel_name','pv_imo','pv_call_sign','pv_flag','pv_year_built','pv_teu','pv_homogeneous','pv_grt','pv_nrt','pv_scantling_draft','pv_dwt','pv_loa','pv_breadth','pv_depth','pv_reefer','pv_class','pv_lane','pv_max_cargo','pv_max_teu','pv_bsa','commitStatus'];
NEEDED.forEach(id => { els[id] = new FakeEl(id); });

const documentMock = {
  getElementById(id) { if (!els[id]) els[id] = new FakeEl(id); return els[id]; },
  createElement() { return new FakeEl('dyn'); },
  querySelectorAll(sel) {
    if (sel && sel.indexOf('parseFuelRows') >= 0) {
      const c = els['parseFuelRows'];
      return c ? c._children.filter(x => !x._isLabel) : [];
    }
    return [];
  }
};

// captured output
let captured = null;
const sandbox = {
  console,
  document: documentMock,
  window: { _particularVessels: [] },
  VESSELS_DATA: [],
  PARTICULAR_DATA: [],
  PORTS_DATA: [], LANES_DATA: [], DIST_RAW: [],
  getGhToken: () => null,
  showParsePreview: (v, p, b) => { captured = { v, p, b }; },
  openTokenSetup: () => {},
  showToast: () => {},
  setCommitStatus: () => {},
  renderDmVessels: () => {},
  renderVesselInfoList: () => {},
  closeParseVesselModal: () => {},
  normalizeName: () => '',
  putGhFile: async () => true,
  appendLineAndPut: async () => true,
  reloadCommittedData: async () => {},
};
vm.createContext(sandbox);
vm.runInContext(code, sandbox);

// override addParseFuelRow so it builds queryable rows (real one only sets innerHTML string)
sandbox.addParseFuelRow = function (data) {
  data = data || { speed:'',lsfo:'',hsfo:'',mgo:'',port_lsfo:'',port_mgo:'' };
  const container = documentMock.getElementById('parseFuelRows');
  const row = documentMock.createElement('div');
  row._inputs = [
    { value: data.speed }, { value: data.lsfo }, { value: data.hsfo },
    { value: data.mgo }, { value: data.port_lsfo }, { value: data.port_mgo },
  ];
  if (container._children.length === 0) {
    const label = documentMock.createElement('div'); label._isLabel = true; container.appendChild(label);
  }
  container.appendChild(row);
};

// ---- assertions ----
let total = 0, pass = 0;
function check(name, got, want) {
  const ok = String(got == null ? '' : got) === String(want == null ? '' : want);
  console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${name}`);
  total++; if (ok) pass++;
  return ok;
}

(async () => {
  // initialize PARTICULAR_DATA from the real transposed CSV (as loadParticularData does)
  const realCsv = fs.readFileSync(path.join(ROOT, 'shipping_data/cul_ship_particular.csv'), 'utf8').replace(/\r\n/g, '\n');
  sandbox.PARTICULAR_DATA = sandbox.parseCSV(realCsv);
  const beforeCols = sandbox.particularHeaderKeys().length;
  console.log('PARTICULAR_DATA rows:', sandbox.PARTICULAR_DATA.length, ' header cols (vessels):', beforeCols - 1);

  // Case 2: clean key:value + HSFO (has a real vessel_name)
  const text = `Vessel Name: CUL TEST STAR
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
  const result = sandbox.parseVesselTextClient(text);
  console.log('parsed particular:', JSON.stringify(result.particular));
  console.log('parsed fuel tiers :', result.fuel.length);

  // 1) parse correctness
  check('particular.vessel_name', result.particular.vessel_name, 'CUL TEST STAR');
  check('particular.teu', result.particular.teu, '1800');
  check('particular.homogeneous', result.particular.homogeneous, '1300');
  check('particular.reefer_plugs', result.particular.reefer_plugs, '300');
  check('fuel[0].speed', result.fuel[0].speed, '17');
  check('fuel[0].hsfo', result.fuel[0].hsfo, '48');
  check('fuel[0].port_mgo', result.fuel[0].port_mgo, '4');
  check('fuelType', result.fuelType, 'HSFO');

  // 2) displayParseResult fills the modal fields (proves fieldMap ids exist & map correctly)
  sandbox.displayParseResult(result);
  check('pv_vessel_name filled', els.pv_vessel_name.value, 'CUL TEST STAR');
  check('pv_reefer_plugs filled', els.pv_reefer_plugs.value, '300');      // the previously-broken id
  check('pv_grt filled', els.pv_grt.value, '18500');
  check('pv_scantling_draft filled', els.pv_scantling_draft.value, '9.80');
  check('parseFuelRows built 3 tiers', els.parseFuelRows._children.filter(c=>!c._isLabel).length, 3);

  // 3) set optional loading-capacity fields, then run saveParseVessel (no-token -> captures CSV)
  els.pv_lane.value = 'AEM'; els.pv_max_cargo.value = '1000'; els.pv_max_teu.value = '1800'; els.pv_bsa.value = '12';
  await sandbox.saveParseVessel();

  if (!captured) { console.log('  FAIL  saveParseVessel produced no preview (commit path broke)'); process.exit(1); }
  const vCsv = captured.v, pCsv = captured.p, bCsv = captured.b;
  console.log('\n--- vessels.csv (new rows) ---');
  vCsv.split('\n').filter(l => l.includes('CUL TEST STAR')).forEach(l => console.log('  ' + l));
  console.log('--- cul_ship_particular.csv header ---');
  console.log('  ' + pCsv.split('\n')[0]);

  // 4) vessels.csv correctness
  const vLines = vCsv.split('\n').filter(l => l.split(',')[1] === 'CUL TEST STAR');
  check('vessels.csv has 3 speed rows', vLines.length, 3);
  // header
  check('vessels.csv header', vCsv.split('\n')[0], 'vessel_code,vessel_name,speed_knots,lsfo_mt_day,hsfo_mt_day,mgo_mt_day,portstay_lsfo_mt_day,portstay_mgo_mt_day,hire_daily');
  // verify a sample row exactly
  check('vessels.csv row[0] exact', vLines[0], 'CTS,CUL TEST STAR,17,0,48,0,0,4,0');

  // 5) cul_ship_particular.csv correctness (transposed: new vessel column appended)
  const pHeader = pCsv.split('\n')[0].split(',');
  const newCol = pHeader[pHeader.length - 1];
  check('particular new column name', newCol, 'CUL TEST STAR');
  const pRows = pCsv.split('\n').map(l => l.split(','));
  const headerIdx = i => pRows[0].indexOf(i);
  const colIdx = pHeader.length - 1;
  function cell(label) { const r = pRows.find(r => r[0].replace(/\s\(\d+\)$/,'') === label); return r ? r[colIdx] : undefined; }
  check('TEU row -> 1800', cell('NOMINAL CAPACITY (TEU)'), '1800');
  check('HOMO row -> 1300', cell('HOMO @14 MT'), '1300');
  check('GRT row -> 18500', cell('GRT'), '18500');
  const reefLine = pCsv.split('\n').find(l => l.startsWith('REEFER PLUGS'));
  console.log('  DEBUG colIdx=', colIdx, 'headerLast=', JSON.stringify(pHeader[pHeader.length-1]));
  console.log('  DEBUG REEFER LINE last 3 cells=', JSON.stringify(reefLine ? reefLine.split(',').slice(-3) : null));
  check('REEFER PLUGS row -> 300', cell('REEFER PLUGS'), '300');
  check('CLASS row -> NK', cell('CLASS'), 'NK');
  check('CALL SIGN row -> 3EXX9', cell('CALL SIGN'), '3EXX9');
  check('particular gained exactly 1 column', pHeader.length, beforeCols + 1);

  // 6) bestmodel row built (optional)
  check('bestmodel row built', /CUL TEST STAR,AEM,1000,1800/.test(bCsv), true);

  console.log('\n==========================================');
  console.log(`INTEGRATION RESULT: ${pass}/${total} assertions passed`);
  process.exit(pass === total ? 0 : 1);
})();
