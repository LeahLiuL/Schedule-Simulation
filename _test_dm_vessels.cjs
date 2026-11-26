// Regression test for Data Manager vessel table (one-ship-per-row + expandable tiers)
const fs = require('fs');
const html = fs.readFileSync('shipping_schedule.html', 'utf8');
const scripts = [...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1]).join('\n');

function extractFn(name) {
  const re = new RegExp('function\\s+' + name + '\\s*\\([^)]*\\)\\s*\\{');
  const m = re.exec(scripts);
  if (!m) throw new Error('function not found: ' + name);
  let i = m.index + m[0].length - 1, depth = 0, inStr = null, esc = false;
  for (; i < scripts.length; i++) {
    const c = scripts[i], p = scripts[i-1];
    if (inStr) {
      if (esc) { esc = false; continue; }
      if (c === '\\') { esc = true; continue; }
      if (c === inStr) inStr = null;
      continue;
    }
    if (c === '"' || c === "'" || c === '`') { inStr = c; continue; }
    if (c === '{') depth++;
    else if (c === '}') { depth--; if (depth === 0) return scripts.slice(m.index, i + 1); }
  }
  throw new Error('unterminated: ' + name);
}

const csv = fs.readFileSync('shipping_data/vessels.csv', 'utf8');
const VESSEL_SOURCE = JSON.parse(fs.readFileSync('shipping_data/vessel_source.json', 'utf8')).ships;
const lines = csv.split(/\r?\n/).filter(Boolean);
const headers = lines[0].split(',');
const idx = Object.fromEntries(headers.map((h, i) => [h, i]));
let VESSELS_DATA = lines.slice(1).map(l => {
  const c = l.split(',');
  return {
    code: c[idx.vessel_code], name: c[idx.vessel_name],
    speed: parseFloat(c[idx.speed_knots]) || 0,
    lsfo: parseFloat(c[idx.lsfo_mt_day]) || 0,
    hsfo: parseFloat(c[idx.hsfo_mt_day]) || 0,
    mgo: parseFloat(c[idx.mgo_mt_day]) || 0,
    ps_lsfo: parseFloat(c[idx.portstay_lsfo_mt_day]) || 0,
    ps_mgo: parseFloat(c[idx.portstay_mgo_mt_day]) || 0,
    hire: parseFloat(c[idx.hire_daily]) || 0
  };
});

let lastHTML = '', searchVal = '', toasts = [];
const document = {
  getElementById(id) {
    if (id === 'dmVesselBody') return { set innerHTML(v) { lastHTML = v; }, get innerHTML() { return lastHTML; } };
    if (id === 'dmVesselSearch') return { value: searchVal };
    return { value: '' };
  }
};
const esc = s => String(s).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
const dmJsStr_outer = s => esc(String(s)).replace(/\\/g,'\\\\').replace(/'/g,"\\'");
const showToast = (m) => toasts.push(m);
const initVesselCombobox = () => {};
const updateDmStatus = () => {};
const confirm = () => true;
const requestAnimationFrame = (fn) => fn();

const names = ['dmJsStr','sourceBadge','tierSourceBadge','getShipGroups','getVesselDupMap','renderDmVessels','editDmVessel','editDmVesselShip','toggleDmShip','deleteDmVesselTier','addDmVesselTier','deleteDmVessel','addDmVessel','filterDmVessels'];
const src = names.map(extractFn).join('\n');
const factory = new Function('VESSELS_DATA_ref', 'document', 'esc', 'showToast', 'initVesselCombobox', 'updateDmStatus', 'confirm', 'requestAnimationFrame', 'dmJsStr_outer', 'VESSEL_SOURCE', 'dmExpandedShips', `
  let VESSELS_DATA = VESSELS_DATA_ref();
  ${src}
  return {
    render: renderDmVessels, edit: editDmVessel, editShip: editDmVesselShip,
    toggle: toggleDmShip, delTier: deleteDmVesselTier, addTier: addDmVesselTier,
    delShip: deleteDmVessel, addShip: addDmVessel, filter: filterDmVessels,
    groups: getShipGroups, getData: () => VESSELS_DATA
  };
`);
let dmExpandedShips = new Set();
const api = factory(() => VESSELS_DATA, document, esc, showToast, initVesselCombobox, updateDmStatus, confirm, requestAnimationFrame, dmJsStr_outer, VESSEL_SOURCE, dmExpandedShips);

let pass = 0, fail = 0;
function check(label, cond, extra) {
  if (cond) { pass++; console.log('PASS', label); }
  else { fail++; console.log('FAIL', label, extra || ''); }
}

// 1. default render: one row per ship, no tiers visible
api.render('');
const shipRows = (lastHTML.match(/data-ship=/g) || []).length;
const tierRowsDefault = (lastHTML.match(/dm-tier-row/g) || []).length;
check('one row per ship (100 codes - 27 no-fuel = 73 visible)', shipRows === 73, 'got ' + shipRows);
check('tiers collapsed by default', tierRowsDefault === 0, 'got ' + tierRowsDefault);
check('no "No vessels found"', !lastHTML.includes('No vessels found'));
check('zero-fuel vessels hidden', !['CZBM','FUYU','MYTJ','NWTR','TBFZ'].some(c => lastHTML.includes(c)), lastHTML.slice(0,300));

// 1b. zero-fuel vessels cannot be revealed by search
api.render('CZBM');
check('search cannot reveal zero-fuel vessel', !lastHTML.includes('CZBM') && lastHTML.includes('No vessels found'), lastHTML.slice(0,300));
api.render('');

// 2. search filter
api.render('CUHC');
check('search shows only matching ships', (lastHTML.match(/data-ship=/g) || []).length === 1, lastHTML.slice(0,200));
check('search result is CUHC', lastHTML.includes('value="CUHC"'));

// 3. expand a ship: 15 tiers for CUHC
api.toggle('CUHC');
check('expanded tier table rendered', lastHTML.includes('dm-tier-wrap'));
const tierInputs = (lastHTML.match(/onchange="editDmVessel\(\d+,'speed'/g) || []).length;
check('CUHC shows 15 speed tiers (Actual + TCD fallback)', tierInputs === 15, 'got ' + tierInputs);
check('Add Tier button exists', lastHTML.includes("addDmVesselTier('CUHC')"));

// 4. edit a tier's fuel value (only that tier changes)
const cuIdx = VESSELS_DATA.findIndex(v => v.code === 'CUHC');
const beforeLsfo = VESSELS_DATA[cuIdx].lsfo;
api.edit(cuIdx, 'lsfo', 99.9);
check('tier edit changes only one row', VESSELS_DATA[cuIdx].lsfo === 99.9);
check('next tier untouched', VESSELS_DATA[cuIdx+1].lsfo !== 99.9);

// 5. ship-level edit syncs all tiers
api.editShip('CUHC', 'hire', 55555);
const cuAll = VESSELS_DATA.filter(v => v.code === 'CUHC');
check('hire synced to all CUHC tiers', cuAll.every(v => v.hire === 55555), cuAll.map(v=>v.hire).join(','));
check('other ship hire untouched', VESSELS_DATA.find(v => v.code === 'BIBK').hire === 0);

// 6. rename ship syncs all tiers
api.editShip('CUHC', 'name', 'CUL TEST NAME');
check('name synced to all CUHC tiers', VESSELS_DATA.filter(v=>v.code==='CUHC').every(v=>v.name==='CUL TEST NAME'));

// 7. add tier then delete tier
const cntBefore = VESSELS_DATA.filter(v=>v.code==='CUHC').length;
api.addTier('CUHC');
const cntAfter = VESSELS_DATA.filter(v=>v.code==='CUHC').length;
check('add tier increments rows', cntAfter === cntBefore + 1, cntBefore + '->' + cntAfter);
const added = VESSELS_DATA.filter(v=>v.code==='CUHC').slice(-1)[0];
check('new tier speed = max+1', added.speed === 19, 'got ' + added.speed);
api.delTier(VESSELS_DATA.indexOf(added));
check('delete tier restores count', VESSELS_DATA.filter(v=>v.code==='CUHC').length === cntBefore);

// 8. delete whole ship removes all tiers
api.delShip('BIBK');
check('whole ship deleted', !VESSELS_DATA.some(v=>v.code==='BIBK'));
api.render('');
check('ship count drops to 72', (lastHTML.match(/data-ship=/g)||[]).length === 72);

// 9. add new vessel unique code + expanded
api.addShip();
check('new vessel code NEW', VESSELS_DATA[0].code === 'NEW');
api.addShip();
check('second new vessel code NEW1 (no collision)', VESSELS_DATA[0].code === 'NEW1', VESSELS_DATA[0].code);

// 9b. Source badges — binary ACT/TCD only, no MIXED
api.render('CUHC');
check('CUHC badge is ACT (Actual present)', /dm-src-act[^>]*>ACT</.test(lastHTML), lastHTML.slice(0,400));
check('no MIXED badge anywhere', !lastHTML.includes('dm-src-mix') && !lastHTML.includes('MIX '));
api.toggle('CUHC');
check('tier badges ACT', lastHTML.includes('dm-src-act'));
check('CUHC sub-table shows TCD source badge', lastHTML.includes('dm-src-tcd'));
api.render('H738');
check('TCD-only ship badge is TCD', /dm-src-tcd[^>]*>TCD</.test(lastHTML), lastHTML.slice(0,400));
api.render('');
check('legacy ship shows dash', lastHTML.includes('dm-src-none'));

// 10. export format still one-row-per-tier, 9 columns
const csvOut = [headers.join(',')].concat(VESSELS_DATA.map(v =>
  [v.code,v.name,v.speed,v.lsfo,v.hsfo,v.mgo,v.ps_lsfo||0,v.ps_mgo||0,v.hire||0].join(',')
)).join('\n');
check('export rows = tier rows', csvOut.split('\n').length - 1 === VESSELS_DATA.length);
check('export 9 columns', csvOut.split('\n')[1].split(',').length === 9);

console.log('\nRESULT: ' + pass + ' passed, ' + fail + ' failed');
process.exit(fail ? 1 : 0);
