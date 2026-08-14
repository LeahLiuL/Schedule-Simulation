/* Real TCD acceptance test.
 * 1) Extracts text from the actual PDF/DOCX files on the Desktop using the SAME
 *    libraries + versions the web page uses:
 *      - PDF : pdf.js 3.11.174  (extractPDFText: per-page item.str joined by ' ')
 *      - DOCX: mammoth 1.6.0     (extractRawText -> result.value)
 * 2) Feeds that text into the REAL parseVesselTextClient extracted from the HTML
 *    (no mock of the parser).
 * 3) Prints the full parsed particular + fuel + warnings for human review.
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = 'c:/Users/leahliu/WorkBuddy/20260325092900';
const TCD = 'c:/Users/leahliu/Desktop/TCD';

// ---------- extract the REAL parser source ----------
const html = fs.readFileSync(path.join(ROOT, 'shipping_schedule.html'), 'utf8').replace(/\r\n/g, '\n');
const START = '// Client-side parse function\n';
const END = '\nfunction displayParseResult(result){';
const i = html.indexOf(START), j = html.indexOf(END, i);
if (i < 0 || j < 0) { console.error('markers not found'); process.exit(1); }
const code = html.slice(i, j);
const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(code + '\n;this.parseVesselTextClient = parseVesselTextClient;', sandbox);

// ---------- text extraction (mirrors the browser pipeline) ----------
const WS = 'c:/Users/leahliu/.workbuddy/binaries/node/workspace/node_modules';
async function extractPDFText(buf) {
  const pdfjsLib = require(WS + '/pdfjs-dist/legacy/build/pdf.js');
  pdfjsLib.GlobalWorkerOptions.workerSrc = require.resolve(WS + '/pdfjs-dist/legacy/build/pdf.worker.js');
  const pdf = await pdfjsLib.getDocument({ data: new Uint8Array(buf) }).promise;
  const pages = [];
  for (let p = 1; p <= pdf.numPages; p++) {
    const page = await pdf.getPage(p);
    const content = await page.getTextContent();
    pages.push(layoutPdfText(content.items));
  }
  return pages.join('\n');
}

// Mirror of the browser layoutPdfText() — groups glyphs into lines and only
// inserts a space where the horizontal gap exceeds ~0.3em.
function layoutPdfText(items) {
  const glyphs = items.filter(it => it.str && it.str.trim().length);
  if (!glyphs.length) return '';
  glyphs.sort((a, b) => {
    const ya = a.transform[5], yb = b.transform[5];
    if (Math.abs(ya - yb) > 0.5) return yb - ya;
    return a.transform[4] - b.transform[4];
  });
  const lines = [];
  let cur = null, curY = null;
  glyphs.forEach(g => {
    const h = g.height || 10;
    if (cur === null || Math.abs(g.transform[5] - curY) > h * 0.6 + 1) {
      cur = []; lines.push(cur); curY = g.transform[5];
    }
    cur.push(g);
  });
  return lines.map(ln => {
    let s = '';
    for (let i = 0; i < ln.length; i++) {
      const g = ln[i];
      if (i > 0) {
        const prev = ln[i - 1];
        const gap = g.transform[4] - (prev.transform[4] + (prev.width || 0));
        const em = (g.height || 10);
        if (gap > em * 0.3) s += ' ';
      }
      s += g.str;
    }
    return s;
  }).join('\n');
}
async function extractWordText(buf, fp) {
  const mammoth = require(WS + '/mammoth');
  const res = await mammoth.extractRawText({ path: fp });
  return res.value;
}

function parseFileType(name) {
  const ext = name.split('.').pop().toLowerCase();
  return ext;
}

// ---------- run ----------
(async () => {
  const outDir = path.join(ROOT, 'archive/export_excel/extracted_text');
  fs.mkdirSync(outDir, { recursive: true });
  const files = fs.readdirSync(TCD).filter(f => /\.(pdf|docx?|txt|csv)$/i.test(f));
  files.sort();
  for (const f of files) {
    const fp = path.join(TCD, f);
    const buf = fs.readFileSync(fp);
    const ext = parseFileType(f);
    const safe = f.replace(/[^A-Za-z0-9._-]/g, '_');
    let text;
    try {
      if (ext === 'pdf') text = await extractPDFText(buf);
      else if (ext === 'docx' || ext === 'doc') text = await extractWordText(buf, fp);
      else text = buf.toString('utf8');
    } catch (e) {
      console.log('\n########## FILE: ' + f + ' ##########');
      console.log('!!! TEXT EXTRACTION FAILED: ' + e.message);
      continue;
    }
    // dump raw extracted text for diagnosis
    fs.writeFileSync(path.join(outDir, safe + '.txt'), text, 'utf8');
    // mirror parseVesselText(): trim
    text = text.trim();
    const r = sandbox.parseVesselTextClient(text);
    console.log('\n############################################################');
    console.log('## FILE: ' + f + '  (' + ext + ', ' + buf.length + ' bytes, ' + text.length + ' chars text)');
    console.log('############################################################');
    console.log('success   :', r.success);
    console.log('fuelType  :', r.fuelType);
    console.log('vessel_name:', JSON.stringify(r.particular.vessel_name));
    console.log('--- PARTICULAR ---');
    const pk = ['vessel_name','call_sign','imo','flag','year_built','class','teu','homogeneous','grt','nrt','dwt','scantling_draft','loa','breadth','depth','reefer_plugs'];
    for (const k of pk) console.log('  ' + k.padEnd(16) + ': ' + JSON.stringify(r.particular[k]));
    console.log('--- FUEL TIERS (' + (r.fuel ? r.fuel.length : 0) + ') ---');
    (r.fuel || []).forEach((t, idx) => {
      console.log('  [' + idx + '] speed=' + JSON.stringify(t.speed) +
        ' lsfo=' + JSON.stringify(t.lsfo) + ' hsfo=' + JSON.stringify(t.hsfo) +
        ' mgo=' + JSON.stringify(t.mgo) + ' port_lsfo=' + JSON.stringify(t.port_lsfo) +
        ' port_mgo=' + JSON.stringify(t.port_mgo));
    });
    console.log('--- WARNINGS (' + (r.warnings ? r.warnings.length : 0) + ') ---');
    (r.warnings || []).forEach(w => console.log('  ! ' + w));
    if(r.fuelRemark) console.log('--- FUEL REMARK ---\n  ' + r.fuelRemark);
    console.log('--- DEBUG interest ---');
    console.log('  ' + JSON.stringify(r.debug));
  }
  console.log('\n========== DONE ==========');
})();
