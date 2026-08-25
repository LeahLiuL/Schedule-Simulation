// Test: ZGYC narrative TCD format "speed about X with consumption Y MT"
// Verifies that extractSpeedPairs now handles "speed about" (no knots unit)
// and that underscore normalization (35_MT -> 35 MT) works.
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const html = fs.readFileSync(path.join(__dirname, '..', '..', 'shipping_schedule.html'), 'utf8').replace(/\r\n/g, '\n');

// Slice parseVesselTextClient from the HTML (same markers as test_parse_harness)
const START = '// Client-side parse function\n';
const END = '\nfunction displayParseResult(result){';
const si = html.indexOf(START);
const ei = html.indexOf(END, si);
if (si < 0 || ei < 0) { console.error('FAIL: cannot locate parser markers'); process.exit(1); }
const src = html.slice(si, ei);

// Minimal DOM mock
const sb = {};
vm.createContext(sb);
vm.runInContext(src + '\n;this.parseVesselTextClient = parseVesselTextClient;', sb);

// ZGYC TCD text (as user provided)
const tcd = `Sea speed consumption:

engine output 25 %, RPM 61, speed about 10 with consumption 16.5 MT
engine output 35%, RPM 69, speed about 11 with consumption 22.5 MT
engine output 45%, RPM 75, speed about 12 with consumption 28 MT
engine output 58 %, RPM 81, speed about 13 with consumption 35_MT
engine output 72%, RPM 87, speed about 14 with consumption 44 MT
engine output 85%, RPM 92, speed about 15 with consumption 51_MT
Max engine output 80 %, RPM 90, speed about 14.5 with consumption 48 MT
Aux. Engines consumption at sea:

The fuel consumption figure assumes good sea conditions, favorable weather, and no refrigerated containers carried.

Aux. Engines consumption at sea: 
About2.3mts LFO RMG 380 CST per day without reefers, Plus abt 10 mts LFO RMG 380 CST per day with full reefer containers connected.(shaft generator in use at sea without consumption LSFO for Aux. generator within load 950KW)
Port consumption:about: A/E 2.3mts + boiler 1.2mts .`;

const r = sb.parseVesselTextClient(tcd);

console.log('=== Fuel Tiers ===');
r.fuel.forEach(t => console.log(`  ${t.speed} kn: LSFO=${t.lsfo} HSFO=${t.hsfo} MGO=${t.mgo}`));
console.log('=== Debug ===');
console.log('  meBySpeed:', JSON.stringify(r.debug.meBySpeed));
console.log('  seaAdd:', JSON.stringify(r.debug.seaAdd));
console.log('  portAdd:', JSON.stringify(r.debug.portAdd));
console.log('  fuelType:', r.fuelType);
console.log('  fuelRemark:', r.fuelRemark || '(none)');
console.log('  warnings:', r.warnings);

// Assertions
const expected = {
  '10': 18.8,   // 16.5 + 2.3
  '11': 24.8,   // 22.5 + 2.3
  '12': 30.3,   // 28 + 2.3
  '13': 37.3,   // 35 + 2.3
  '14': 46.3,   // 44 + 2.3
  '14.5': 50.3, // 48 + 2.3
  '15': 53.3,   // 51 + 2.3
};

let pass = 0, fail = 0;
for (const [sp, val] of Object.entries(expected)) {
  const tier = r.fuel.find(t => String(t.speed) === sp);
  if (!tier) { console.error(`FAIL: no tier for ${sp} kn`); fail++; continue; }
  const total = (tier.lsfo || 0) + (tier.hsfo || 0) + (tier.mgo || 0);
  if (Math.abs(total - val) < 0.01) { console.log(`PASS: ${sp} kn = ${total}`); pass++; }
  else { console.error(`FAIL: ${sp} kn expected ${val}, got ${total}`); fail++; }
}

// Check seaAdd (aux 2.3)
const seaTotal = (r.debug.seaAdd.LSFO||0) + (r.debug.seaAdd.HSFO||0) + (r.debug.seaAdd.MGO||0);
if (Math.abs(seaTotal - 2.3) < 0.01) { console.log('PASS: seaAdd = 2.3'); pass++; }
else { console.error(`FAIL: seaAdd expected 2.3, got ${seaTotal}`); fail++; }

// Check portAdd (A/E 2.3 + boiler 1.2 = 3.5)
const portTotal = (r.debug.portAdd.LSFO||0) + (r.debug.portAdd.HSFO||0) + (r.debug.portAdd.MGO||0);
if (Math.abs(portTotal - 3.5) < 0.01) { console.log('PASS: portAdd = 3.5'); pass++; }
else { console.error(`FAIL: portAdd expected 3.5, got ${portTotal}`); fail++; }

console.log(`\n=== Result: ${pass} pass, ${fail} fail ===`);
process.exit(fail > 0 ? 1 : 0);
