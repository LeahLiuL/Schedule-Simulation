// Verify parseWordContent magic-byte preflight:
//   1. Old .doc (OLE2 header) → clear "请另存为 .docx" error, no mammoth call
//   2. Plain-text vessel data with .docx extension → fallback to text pipeline
//   3. Real .docx (zip header) → proceeds to mammoth (we don't load mammoth in test,
//      so we just verify isZip branch is taken without the toast error)
//
// Slice the function from the page and run it with a DOM mock that captures
// showToast calls and parseVesselText invocations.

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const html = fs.readFileSync('shipping_schedule.html', 'utf8').replace(/\r\n/g, '\n');
const si = html.indexOf('function parseWordContent(');
const ei = html.indexOf('\nfunction extractWordText(', si);
if (si < 0 || ei < 0) { console.error('FAIL: cannot locate parseWordContent'); process.exit(1); }
const src = html.slice(si, ei);

const toasts = [];
const parsed = [];
const sb = {
  console, Math, JSON, Date,
  document: {
    getElementById: () => ({ value: '', style: {}, classList: { add(){}, remove(){} }, innerHTML: '', textContent: '' }),
    createElement: () => ({ setAttribute(){}, appendChild(){}, onload: null, onerror: null }),
    head: { appendChild(){} }
  },
  showToast: (msg, type, dur) => toasts.push({ msg, type, dur }),
  parseVesselText: () => parsed.push('called'),
  TextDecoder: global.TextDecoder
};
vm.createContext(sb);
vm.runInContext(src + ';this.parseWordContent = parseWordContent;', sb);

function bytes(b) { return new Uint8Array(b); }
function bufFrom(arr) {
  const u8 = new Uint8Array(arr.length);
  arr.forEach((b, i) => { u8[i] = b; });
  // Make a real ArrayBuffer (not SharedArrayBuffer) so mammoth-style consumers can read it
  return u8.buffer.slice(u8.byteOffset, u8.byteOffset + u8.byteLength);
}

// === Case 1: OLE2 header (old .doc) ===
toasts.length = 0; parsed.length = 0;
const ole2 = [0xD0,0xCF,0x11,0xE0,0xA1,0xB1,0x1A,0xE1, 0,0,0,0,0,0,0,0];
sb.parseWordContent(bufFrom(ole2), 'old.doc');
const c1 = toasts.length === 1 && toasts[0].type === 'error' && /旧版 .doc/.test(toasts[0].msg) && toasts[0].dur >= 5000 && parsed.length === 0;
console.log('OLE2 旧版 .doc         :', c1 ? 'PASS' : 'FAIL', JSON.stringify(toasts));

// === Case 2: Plain text vessel data with .docx extension ===
toasts.length = 0; parsed.length = 0;
const utf8 = (s) => Array.from(Buffer.from(s, 'utf8'));
const text = 'VESSEL NAME: KOTA EXPRESS\nTEU: 1850\nDWT: 23500 MT\nFLAG: Singapore';
const tBuf = bufFrom(utf8(text));
sb.parseWordContent(tBuf, 'notes.docx');
const c2 = toasts.length === 1 && toasts[0].type === 'warn' && /纯文本/.test(toasts[0].msg) && parsed.length === 1;
console.log('纯文本伪装 .docx      :', c2 ? 'PASS' : 'FAIL', JSON.stringify(toasts));

// === Case 3: Plain text but no vessel keywords → still error ===
toasts.length = 0; parsed.length = 0;
sb.parseWordContent(bufFrom(utf8('hello world foo bar baz qux')), 'garbage.docx');
const c3 = toasts.length === 1 && toasts[0].type === 'error' && /不是有效的 .docx/.test(toasts[0].msg) && parsed.length === 0;
console.log('无关纯文本 .docx     :', c3 ? 'PASS' : 'FAIL', JSON.stringify(toasts));

// === Case 4: Real zip header → proceeds past preflight (we expect "Parsing Word..." info toast) ===
toasts.length = 0; parsed.length = 0;
const zipHeader = [0x50, 0x4B, 0x03, 0x04, 0x14, 0x00, 0x00, 0x00]; // PK\x03\x04 + extra
// We do NOT mock mammoth; the script onload won't fire and no toast error should appear.
// Just verify that isZip branch is taken (i.e., we get the "Parsing Word..." toast).
sb.parseWordContent(bufFrom(zipHeader), 'real.docx');
// After "Parsing Word..." info toast, the script load happens. We won't see that complete.
// We only check that NO error toast appeared in the synchronous portion.
const c4 = !toasts.some(t => t.type === 'error');
console.log('真 .docx (zip 头)   :', c4 ? 'PASS' : 'FAIL', JSON.stringify(toasts));

const ok = c1 && c2 && c3 && c4;
console.log('---');
console.log(ok ? 'ALL PASS' : 'FAIL');
process.exit(ok ? 0 : 1);