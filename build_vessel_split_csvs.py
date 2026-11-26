"""
Split shipping_data/vessels.csv into source-separated CSVs, then rebuild the
merged file from those three parts.

Source of truth for the split:
  - shipping_data/vessel_source.json  (per-tier ACT / TCD attribution, originally
    generated from the two sheets of Vessel Daily Consumption.xlsx)
  - shipping_data/vessels.csv         (current merged values, kept byte-identical)

Output files (all use the fixed 9-column schema, CRLF, no BOM):
  HSFO from Excel is never written (stays 0 in ACT/TCD files); the pre-existing
  N1385 HSFO exception in LEGACY is preserved untouched.
  shipping_data/vessels_actual.csv   rows attributed to Actual Daily Consumption
  shipping_data/vessels_tcd.csv      rows attributed to TCD Daily Consumption
  shipping_data/vessels_legacy.csv   all remaining rows (pre-Excel data, no-fuel
                                     placeholders, extra speed tiers)
  shipping_data/vessels.csv          union of the three, sorted by (code, speed)

Why values are copied from vessels.csv instead of being re-read from Excel:
  The agreed rule is "Excel zero/empty never clears an existing nonzero value",
  so 97 tiers currently hold a value that Excel does not have.  Re-reading Excel
  verbatim would silently erase those.  The script cross-checks against Excel
  and reports differences, but never changes the numbers.

Usage:
  python build_vessel_split_csvs.py            # dry-run
  python build_vessel_split_csvs.py write      # apply
"""
import csv
import datetime
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, 'shipping_data')
MERGED = os.path.join(DATA, 'vessels.csv')
SOURCE = os.path.join(DATA, 'vessel_source.json')
OUT = {
    'ACT': os.path.join(DATA, 'vessels_actual.csv'),
    'TCD': os.path.join(DATA, 'vessels_tcd.csv'),
    'LEGACY': os.path.join(DATA, 'vessels_legacy.csv'),
}
XLSX = (r'P:\04 上海操作中心\01 船期管理科\船期管理\VSL Daily Movement'
        r'\更新\Vessel Daily Consumption.xlsx')

FIELDS = ['vessel_code', 'vessel_name', 'speed_knots', 'lsfo_mt_day',
          'hsfo_mt_day', 'mgo_mt_day', 'portstay_lsfo_mt_day',
          'portstay_mgo_mt_day', 'hire_daily']
WRITE = len(sys.argv) > 1 and sys.argv[1].lower() == 'write'

# Excel codes that were folded into the Port Charges canonical codes.
EXCEL_CODE_TO_PC = {
    'CASR': 'ASRR', 'CUML': 'CUMN', 'CUST': 'SHTG', 'KRCB': 'KRCL',
    'RACINE': 'RACE', 'SDAM': 'SHTG', 'SISO': 'SNSO', 'STBL': 'STBE',
    'XHDL': 'XHDP', 'ZGXA': 'ZGOA',
}
XLSX_SHEETS = {'ACT': ('Actual Daily Consumption', 3),
               'TCD': ('TCD Daily Consumption', 2)}


def num(x):
    try:
        return float(x) if x not in (None, '') else 0.0
    except (TypeError, ValueError):
        return 0.0


def read_csv(path):
    raw = open(path, 'rb').read().decode('utf-8-sig')
    lines = raw.splitlines()
    assert lines[0] == ','.join(FIELDS), ('unexpected header', lines[0])
    rows = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        parts = ln.split(',')
        assert len(parts) == 9, ('bad column count', ln)
        rows.append(parts)
    return raw, rows


def serialise(rows):
    return (','.join(FIELDS) + '\r\n' +
            '\r\n'.join(','.join(r) for r in rows) + '\r\n').encode('utf-8')


def excel_lookup():
    """Return {(pc_code, speed): [lsfo, mgo, ps_lsfo, ps_mgo]} for each sheet."""
    try:
        import openpyxl
    except ImportError:
        return {}
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    result = {}
    for tag, (sheet_name, start) in XLSX_SHEETS.items():
        ws = wb[sheet_name]
        # Actual sheet has an extra duplicate header row at row 2.
        out, code = {}, None
        for r in ws.iter_rows(min_row=start, values_only=True):
            c, n, spd = (list(r) + [None] * 8)[:3]
            if c not in (None, ''):
                code = str(c).strip()
            if code and spd not in (None, ''):
                v = [num(x) for x in (list(r) + [None] * 8)[3:8]]
                key = (EXCEL_CODE_TO_PC.get(code, code), round(float(spd), 2))
                out[key] = [v[0], v[2], v[3], v[4]]  # skip HSFO
        result[tag] = out
    return result


def main():
    raw, rows = read_csv(MERGED)
    source = json.load(open(SOURCE, encoding='utf-8'))['ships']

    groups = {'ACT': [], 'TCD': [], 'LEGACY': []}
    for r in rows:
        code, spd = r[0], '%g' % num(r[2])
        tag = source.get(code, {}).get('tiers', {}).get(spd, 'LEGACY')
        groups[tag].append(r)

    # Cross-check against Excel (report only, never rewrite values).
    excel = excel_lookup()
    cmp = {'match': 0, 'excel_zero_kept': 0, 'differs': 0, 'no_excel_row': 0}
    samples = []
    for tag in ('ACT', 'TCD'):
        for r in groups[tag]:
            key = (r[0], round(num(r[2]), 2))
            ex = excel.get(tag, {}).get(key)
            if ex is None:
                cmp['no_excel_row'] += 1
                continue
            cur = [num(r[3]), num(r[5]), num(r[6]), num(r[7])]
            if all(x <= 0 for x in ex):
                cmp['excel_zero_kept'] += 1
            elif all(abs(x - y) < 0.051 for x, y in zip(ex, cur)):
                cmp['match'] += 1
            else:
                cmp['differs'] += 1
                if len(samples) < 5:
                    samples.append((tag, key, ex, cur))

    rebuilt = sorted((r for part in groups.values() for r in part),
                     key=lambda r: (r[0], num(r[2])))
    rebuilt_bytes = serialise(rebuilt)
    same = rebuilt_bytes == raw.encode('utf-8')
    print('rows total', len(rows),
          '| ACT', len(groups['ACT']),
          '| TCD', len(groups['TCD']),
          '| LEGACY', len(groups['LEGACY']))
    print('excel cross-check', cmp)
    for s in samples:
        print('   differs sample', s)
    print('merged rebuild identical to current vessels.csv:', same)
    if not same:
        print('ABORT: rebuild differs; nothing written.')
        return

    if not WRITE:
        print('\nDRY-RUN only. Use `write` to apply.')
        return

    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = os.path.join(ROOT, 'archive', 'backup')
    os.makedirs(backup, exist_ok=True)
    targets = [MERGED, SOURCE] + [p for p in OUT.values() if os.path.exists(p)]
    for p in targets:
        shutil.copyfile(p, os.path.join(
            backup, os.path.basename(p).replace('.csv', '_%s.csv' % stamp)
            .replace('.json', '_%s.json' % stamp)))

    for tag, path in OUT.items():
        open(path, 'wb').write(serialise(groups[tag]))
        print('written', os.path.relpath(path, ROOT), len(groups[tag]), 'rows')

    print('backup ->', os.path.relpath(backup, ROOT), 'stamp', stamp)


if __name__ == '__main__':
    main()
