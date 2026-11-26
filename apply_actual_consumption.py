"""
Merge Actual Daily Consumption (primary) + TCD Daily Consumption (fallback)
from P:\\...\\Vessel Daily Consumption.xlsx into shipping_data/vessels.csv.

Rules (user confirmed 2026-11-26):
  - Source priority: Actual > TCD for the SAME (code, speed) key.
  - Existing CSV nonzero values:
      * ACTUAL conflict -> overwrite with Actual value
      * TCD    conflict -> KEEP existing CSV value
  - CSV zero/empty fields -> fill from merged source (any).
  - HSFO column -> ALWAYS keep 0 (never write).
  - New (code, speed) rows -> append with all values; hsfo=0.
      * hire_daily: inherit from same code's existing rows if any, else 0.
  - Never delete rows not covered by Excel.
  - Keep CRLF line endings, no BOM.

Usage: python apply_actual_consumption.py        (dry-run)
       python apply_actual_consumption.py write  (apply)
"""
import csv, os, sys, shutil, datetime

XLSX = r'P:\04 上海操作中心\01 船期管理科\船期管理\VSL Daily Movement\更新\Vessel Daily Consumption.xlsx'
CSV  = 'shipping_data/vessels.csv'
WRITE = len(sys.argv) > 1 and sys.argv[1].lower() == 'write'

FIELDS = ['vessel_code','vessel_name','speed_knots','lsfo_mt_day','hsfo_mt_day',
          'mgo_mt_day','portstay_lsfo_mt_day','portstay_mgo_mt_day','hire_daily']
XLSX_IDX = {'lsfo':3,'hsfo':4,'mgo':5,'ps_lsfo':6,'ps_mgo':7}
CSV_FIELD = {'lsfo':'lsfo_mt_day','hsfo':'hsfo_mt_day','mgo':'mgo_mt_day',
             'ps_lsfo':'portstay_lsfo_mt_day','ps_mgo':'portstay_mgo_mt_day'}


def num(x):
    if x is None or x == '': return 0.0
    try: return float(x)
    except (ValueError, TypeError): return 0.0


def fmt(v):
    if isinstance(v, float) and v.is_integer(): return str(int(v))
    return str(v)


def parse_sheet(ws, start_row):
    rows, code, name = [], None, None
    for r in ws.iter_rows(min_row=start_row, values_only=True):
        c, n, spd = (list(r) + [None]*8)[:3]
        if c not in (None, ''):
            code, name = str(c).strip(), str(n or '').strip()
        if code is None or spd in (None, ''):
            continue
        vals = [num(x) for x in (list(r) + [None]*8)[3:8]]
        rows.append({'code':code, 'name':name, 'speed':num(spd),
                     'lsfo':vals[0], 'hsfo':vals[1], 'mgo':vals[2],
                     'ps_lsfo':vals[3], 'ps_mgo':vals[4]})
    return rows


def main():
    import openpyxl
    wb = openpyxl.load_workbook(XLSX, data_only=True, read_only=True)
    tcd = parse_sheet(wb['TCD Daily Consumption'], 2)
    act = parse_sheet(wb['Actual Daily Consumption'], 3)

    def key(r): return (r['code'], round(num(r['speed']), 2))
    merged, src = {}, {}
    for r in tcd:
        merged[key(r)] = r; src[key(r)] = 'TCD'
    for r in act:                      # Actual wins for same (code, speed)
        merged[key(r)] = r; src[key(r)] = 'ACT'

    # read CSV preserving CRLF
    raw = open(CSV, 'rb').read().decode('utf-8-sig')
    lines = raw.splitlines()
    headers = lines[0].split(',')
    assert headers == FIELDS, (headers, FIELDS)
    records = []
    for ln in lines[1:]:
        if not ln.strip(): continue
        c = ln.split(',')
        while len(c) < 9: c.append('')
        records.append(dict(zip(FIELDS, c[:9])))

    cur = {}
    for i, r in enumerate(records):
        cur[(r['vessel_code'], round(num(r['speed_knots']), 2))] = i

    stats = {'overwrite':[], 'fill':[], 'new':[], 'kept_conflict':[], 'hsfo_blocked':[]}

    for k, ex in sorted(merged.items()):
        source = src[k]
        if k not in cur:
            hire = 0
            for r in records:
                if r['vessel_code'] == k[0] and num(r['hire_daily']) > 0:
                    hire = num(r['hire_daily']); break
            rec = {
                'vessel_code':k[0], 'vessel_name':ex['name'], 'speed_knots':fmt(ex['speed']),
                'lsfo_mt_day':fmt(ex['lsfo']), 'hsfo_mt_day':'0', 'mgo_mt_day':fmt(ex['mgo']),
                'portstay_lsfo_mt_day':fmt(ex['ps_lsfo']), 'portstay_mgo_mt_day':fmt(ex['ps_mgo']),
                'hire_daily':fmt(hire)
            }
            records.append(rec); cur[k] = len(records)-1
            stats['new'].append((k, source, rec)); continue

        r = records[cur[k]]
        # vessel name: fill only if empty (never overwrite)
        if not r['vessel_name'].strip() and ex['name']:
            r['vessel_name'] = ex['name']

        for f, idx in XLSX_IDX.items():
            nv = num(ex[f]); cf = CSV_FIELD[f]; ov = num(r[cf] or 0)
            if f == 'hsfo':
                if ov == 0 and nv > 0:
                    stats['hsfo_blocked'].append((k, source, nv))
                r[cf] = '0'             # iron rule: HSFO always 0
                continue
            if nv <= 0:
                continue                      # Excel 0/empty -> never clear existing data
            if ov == 0:
                r[cf] = fmt(nv); stats['fill'].append((k, f, nv, source))
            elif abs(nv - ov) > 0.05:
                if source == 'ACT':
                    r[cf] = fmt(nv); stats['overwrite'].append((k, f, ov, nv, source))
                else:
                    stats['kept_conflict'].append((k, f, ov, nv, source))

    # write CSV with CRLF, no BOM
    if WRITE:
        os.makedirs('archive/backup', exist_ok=True)
        stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        shutil.copyfile(CSV, 'archive/backup/vessels_%s.csv' % stamp)
        out = ','.join(FIELDS) + '\r\n' + '\r\n'.join(
            ','.join(rec[f] for f in FIELDS) for rec in records) + '\r\n'
        open(CSV, 'wb').write(out.encode('utf-8'))
        print('WRITTEN. backup -> archive/backup/vessels_%s.csv' % stamp)
    else:
        print('DRY-RUN (no file written). Use `write` to apply.\n')

    for name in ['new','fill','overwrite','kept_conflict','hsfo_blocked']:
        items = stats[name]
        print('\n=== %s: %d' % (name, len(items)))
        for it in items[:20]:
            print('   ', it)
        if len(items) > 20: print('    ... (%d more)' % (len(items)-20))

    print('\nSUMMARY: rows %d -> %d, ships %d -> %d' % (
        len(lines)-1, len(records),
        len(set(ln.split(',')[0] for ln in lines[1:] if ln.strip())),
        len(set(r['vessel_code'] for r in records))))


if __name__ == '__main__':
    main()
