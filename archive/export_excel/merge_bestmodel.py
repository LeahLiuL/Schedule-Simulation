#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Merge CUL Vessel Best Model Excel report into cul_vessel_bestmodel.csv.

Iron rule (from project MEMORY.md):
- Base = current cul_vessel_bestmodel.csv (never delete CSV-only rows).
- Excel overrides a field ONLY when it has a non-empty value.
- Vessel matched by normalized name; lane matched by token-overlap fallback
  (combined lane "AEM/REX" falls back to split rows "AEM" / "REX").
- Vessels/lanes present in Excel but not in CSV are ADDED.
- Excel has no Remark column -> existing rows keep their Remark; new rows get ''.

Usage: set DRY=False to write.
"""
import csv, re, zipfile, sys
from xml.etree import ElementTree as ET

XLSX = r"C:\CULINES\Claw Report\CUL Vessel Best Model Report - 2026.xlsx"
CSV  = 'shipping_data/cul_vessel_bestmodel.csv'
DRY  = (len(sys.argv) <= 1 or sys.argv[1] != 'write')

M = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'

def clean_cell(v):
    if v is None:
        return ''
    s = str(v).replace('\n', ' ').replace('\r', ' ')
    s = re.sub(r'\s+', ' ', s).strip()
    if s in ('/', '-', 'N/A', 'NA', 'NIL', 'NIL.', 'NONE', ''):
        return ''
    return s

def norm_key(s):
    return re.sub(r'[^A-Z0-9]', '', s.upper())

def lane_tokens(s):
    return set(t for t in re.split(r'[/\s()]+', s.upper()) if t)

def lane_match(elane, etok, clane, ctok):
    """Strict lane match (avoids loose token-overlap like CST(NB)~CST(SB)).

    - exact normalized string equality, OR
    - one lane's token set is a (non-empty) subset of the other's
      (covers combined lane 'AEM/REX' falling back to split rows 'AEM'/'REX').
    """
    if elane == clane:
        return True
    if etok and ctok and (ctok <= etok or etok <= ctok):
        return True
    return False

# ---- parse Excel ----
z = zipfile.ZipFile(XLSX)
sst = ET.fromstring(z.read('xl/sharedStrings.xml'))
sis = [''.join(n.text or '' for n in el.iter('{%s}t' % M)) for el in sst.findall('{%s}si' % M)]
ws = ET.fromstring(z.read('xl/worksheets/sheet1.xml'))

def col_of(ref):
    return re.match(r'[A-Z]+', ref).group()

def cells(row):
    d = {}
    for c in row.findall('{%s}c' % M):
        ref = c.get('r'); t = c.get('t'); v = c.find('{%s}v' % M)
        val = ''
        if v is not None:
            val = sis[int(v.text)] if t == 's' and int(v.text) < len(sis) else (v.text or '')
        else:
            isn = c.find('{%s}is' % M)
            if isn is not None:
                val = ''.join(n.text or '' for n in isn.iter('{%s}t' % M))
        d[col_of(ref)] = val
    return d

# Excel col -> CSV col index (Excel G 'Max TEU' (2nd) maps to CSV 'Max TEU2')
EXCEL_COLS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K']
xrows = []
for r in ws.findall('.//{%s}row' % M):
    if r.get('r') == '1':
        continue  # header
    d = cells(r)
    if not any(d.values()):
        continue
    rec = [clean_cell(d.get(col, '')) for col in EXCEL_COLS]
    if rec[0] == '':
        continue
    xrows.append(rec)

# ---- read current CSV ----
with open(CSV, encoding='utf-8-sig', newline='') as f:
    reader = csv.reader(f)
    header = next(reader)
    csv_rows = [row + [''] * (12 - len(row)) for row in reader]

csv_index = {}
for i, row in enumerate(csv_rows):
    csv_index[i] = (norm_key(row[0]), lane_tokens(row[1]))

updates = []      # (i, name, lane, [(col, newval)...])
additions = []
matched_csv = set()
consumed = set()   # csv rows already written by a prior Excel row (avoid re-collapsing dup Excel rows)

for rec in xrows:
    name = rec[0]; lane = rec[1]
    vkey = norm_key(name); ltk = lane_tokens(lane)
    hits = [i for i, (vk, lt) in csv_index.items()
            if vk == vkey and lane_match(lane, ltk, csv_rows[i][1], lt)]
    if DRY and vkey == 'CULYANGPU':
        print("  [DBG] Excel %-18s lane=%r ltk=%s -> hits=%s" % (name, lane, sorted(ltk), hits))
    if not hits:
        # vessel/lane not present in CSV -> add as NEW row (user: "没有的加一下")
        additions.append(rec[:11] + [''])
        continue
    # Among matched csv rows, update only the FIRST row per DISTINCT lane string.
    # - combined lane 'AEM/CGX/REX' hits 'AEM/CGX' AND 'REX' (different lanes) -> both updated.
    # - duplicate lane 'SJA' (laden + empties rows) -> only first updated, preserving the 2nd.
    fresh = [i for i in hits if i not in consumed]
    seen_lane = set()
    pick = []
    for i in fresh:
        ln = csv_rows[i][1]
        if ln not in seen_lane:
            seen_lane.add(ln)
            pick.append(i)
    if not pick:
        continue
    for i in pick:
        matched_csv.add(i)
        consumed.add(i)
        row = csv_rows[i]
        changed = []
        for ci in range(2, 11):  # ONLY capacity fields 2..10
                                # (Vessel Name=0, Service Lane=1 are keys; Remark=11 Excel lacks)
            ev = rec[ci] if ci < len(rec) else ''
            if ev != '' and ev != row[ci]:
                row[ci] = ev
                changed.append((ci, ev))
        if changed:
            updates.append((i, row[0], row[1], changed))

merged = list(csv_rows)
for nr in additions:
    merged.append(nr)

# ---- report ----
print(f"Excel data rows       : {len(xrows)}")
print(f"CSV data rows (base)  : {len(csv_rows)}")
print(f"Updated existing rows : {len(updates)}")
for i, name, lane, ch in updates:
    print("  UPDATE %-22s [%-10s] %s" % (name, lane,
          ", ".join("%s=%s" % (header[c], v) for c, v in ch)))
print(f"New additions         : {len(additions)}")
for nr in additions:
    print("  ADD    %-22s [%-10s] cap=%s reefer=%s" % (nr[0], nr[1], nr[2], nr[10]))
csv_only = [i for i in csv_index if i not in matched_csv]
print(f"CSV-only rows kept    : {len(csv_only)}")
for i in csv_only:
    print("  KEEP   %-22s [%s]" % (csv_rows[i][0], csv_rows[i][1]))

if not DRY:
    with open(CSV, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(merged)
    print("\nWROTE", CSV)
else:
    print("\n[DRY RUN] no file written.")
