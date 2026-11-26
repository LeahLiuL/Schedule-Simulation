#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Align vessels.csv vessel codes to Port Charges shipCode convention.

User decision 2026-11-26:
  - Use Port Charges codes as the code authority.
  - Rename the 4 Full-Schedule canonical codes back to their Port Charges codes:
      CUML -> CUMN, SISO -> SNSO, XHDL -> XHDP, ZGXA -> ZGOA
  - Add 5 Port-Charge-only vessels with no fuel data (one 14kn zero placeholder row each).
  - Keep CSV-only vessels with real fuel data (do NOT delete them).

Usage:
  python align_portcharge_codes.py          # dry run
  python align_portcharge_codes.py write    # backup + write
"""
import csv, datetime, json, os, re, shutil, sys
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(ROOT, 'shipping_data', 'vessels.csv')
SRC = os.path.join(ROOT, 'shipping_data', 'vessel_source.json')
HTML = os.path.join(ROOT, 'port_charges_inquiry.html')

# Full Schedule canonical -> Port Charges historical code
RENAME = {
    'CUML': 'CUMN',
    'SISO': 'SNSO',
    'XHDL': 'XHDP',
    'ZGXA': 'ZGOA',
}

# code -> best-known name (MYTJ has no name source; leave blank rather than invent)
ADD = [
    ('CZBM', 'ZBM'),
    ('FUYU', 'FU YU'),
    ('MYTJ', ''),
    ('NWTR', 'NEW THINKER'),
    ('TBFZ', 'TB FENGZE'),
]

# 14kn is used instead of 0kn: getUniqueVessels() takes the first row as the default,
# and a speed=0 all-zero row would make low-speed interpolation start from 0.
PLACEHOLDER_SPEED = '14'


def read_csv():
    raw = open(CSV, 'rb').read()
    bom = raw.startswith(b'\xef\xbb\xbf')
    text = raw.decode('utf-8-sig' if bom else 'utf-8')
    lines = text.splitlines()
    header = lines[0]
    rows = [next(csv.reader([ln])) for ln in lines[1:] if ln.strip()]
    return bom, header, rows


def portcharge_codes():
    s = open(HTML, encoding='utf-8', errors='ignore').read()
    return set(re.findall(r'"shipCode"\s*:\s*"([^"]+)"', s))


def num(x):
    try:
        return float(x or 0)
    except Exception:
        return 0.0


def main():
    write = 'write' in sys.argv[1:]
    bom, header, rows = read_csv()
    assert len(header.split(',')) == 9, 'vessels.csv must have 9 columns'
    assert all(len(r) == 9 for r in rows), 'found row with != 9 columns'

    pc = portcharge_codes()
    before_codes = {r[0] for r in rows}
    stats = Counter()

    # 1) rename canonical codes back to Port Charges codes
    for r in rows:
        old = r[0]
        if old in RENAME:
            r[0] = RENAME[old]
            stats['renamed_' + old + '->' + r[0]] += 1

    # 2) add Port-Charge-only vessels with no fuel data
    present = {r[0] for r in rows}
    for code, name in ADD:
        if code in present:
            stats['already_present_' + code] += 1
            continue
        rows.append([code, name, PLACEHOLDER_SPEED, '0', '0', '0', '0', '0', '0'])
        stats['added_' + code] += 1

    # 3) sort by code, then speed
    rows.sort(key=lambda r: (r[0], num(r[2])))

    # ---- validation ----
    assert all(len(r) == 9 for r in rows)
    after_codes = {r[0] for r in rows}
    assert len(rows) == len({(r[0], r[2]) for r in rows}), 'duplicate (code,speed) found'
    missing_pc = sorted(pc - after_codes)
    assert not missing_pc, 'Port Charges codes still missing: %s' % missing_pc
    kept_csv_only = sorted(before_codes - pc - set(RENAME.values()))
    print('=== rows %d -> %d ; codes %d -> %d' % (
        len(rows) - sum(stats[k] for k in stats if k.startswith('added_')),
        len(rows), len(before_codes), len(after_codes)))
    print('=== Port Charges unique codes:', len(pc))
    print('=== Port Charges codes covered:', len(pc & after_codes))
    print('=== CSV-only codes kept (with data):', len(kept_csv_only), kept_csv_only)
    for k in sorted(stats):
        print('  ', k, stats[k])

    if not write:
        print('DRY RUN — nothing written.')
        return

    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = os.path.join(ROOT, 'archive', 'backup', 'vessels_%s.csv' % stamp)
    os.makedirs(os.path.dirname(backup), exist_ok=True)
    shutil.copy2(CSV, backup)
    print('BACKUP:', os.path.relpath(backup, ROOT))

    payload = header + '\r\n' + '\r\n'.join(','.join(r) for r in rows) + '\r\n'
    if bom:
        payload = '\ufeff' + payload
    open(CSV, 'wb').write(payload.encode('utf-8'))
    print('WRITTEN:', os.path.relpath(CSV, ROOT))

    # ---- sync vessel_source.json ----
    doc = json.load(open(SRC, encoding='utf-8'))
    ships = doc['ships']
    for old, new in RENAME.items():
        if old in ships:
            obj = ships.pop(old)
            ships[new] = obj
            print('SOURCE MOVED:', old, '->', new)
    doc['note'] = (
        '数据来源二选一：ACT=该船在 Actual Daily Consumption 有数据'
        '（Actual 没有的档位由 TCD 补）；TCD=Actual 完全没有。'
        '船码以 Port Charges 账单 shipCode 为准（2026-11-26 用户拍板）：'
        'CUML/SISO/XHDL/ZGXA 已改回 CUMN/SNSO/XHDP/ZGOA；'
        'CZBM/FUYU/MYTJ/NWTR/TBFZ 为无油耗数据船，未写入本来源表。'
        '有油耗数据但无 Port Charges 账单的船保留不删。'
    )
    with open(SRC, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print('SOURCE JSON synced:', len(ships), 'ships')


if __name__ == '__main__':
    main()
