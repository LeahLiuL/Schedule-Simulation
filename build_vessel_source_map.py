"""
Build shipping_data/vessel_source.json — records which sheet (Actual / TCD)
supplied each vessel's speed-tier fuel data in the 2026-11-26 update.

Structure:
{
  "generated": "2026-11-26",
  "note": "...",
  "ships": {
    "CUHC": {"type":"MIXED","act":13,"tcd":2,
             "tiers":{"11":"TCD","11.5":"TCD","12":"ACT", ...}},
    ...
  }
}

type: ACT (vessel appears in Actual sheet — Actual wins wherever present)
      TCD (vessel absent from Actual, all tiers from TCD fallback)
Only these two values are used; no MIXED state.
Ships not present in either sheet are omitted (no source = legacy CSV value).
"""
import openpyxl, collections, json, datetime

XLSX = r'P:\04 上海操作中心\01 船期管理科\船期管理\VSL Daily Movement\更新\Vessel Daily Consumption.xlsx'
OUT  = 'shipping_data/vessel_source.json'
# Excel code -> Port Charges code; stale duplicate blocks from the 2026-11-26
# dedupe are ignored so they never re-appear as separate ships.
RENAME = {'CASR':'ASRR', 'CUML':'CUMN', 'SISO':'SNSO', 'STBL':'STBE',
          'XHDL':'XHDP', 'ZGXA':'ZGOA'}
IGNORE = {'RACINE', 'CUST', 'KRCB', 'SDAM'}


def parse(ws, start_row):
    out, code = {}, None
    for r in ws.iter_rows(min_row=start_row, values_only=True):
        c, n, spd = (list(r) + [None]*8)[:3]
        if c not in (None, ''):
            code = str(c).strip()
        if code and spd not in (None, ''):
            if code in IGNORE:
                continue
            out[(RENAME.get(code, code), round(float(spd), 2))] = True
    return out


def main():
    wb = openpyxl.load_workbook(XLSX, data_only=True, read_only=True)
    tcd = parse(wb['TCD Daily Consumption'], 2)
    act = parse(wb['Actual Daily Consumption'], 3)
    # Actual wins for same (code, speed)
    tiers = {}
    for k in tcd: tiers[k] = 'TCD'
    for k in act: tiers[k] = 'ACT'

    by = collections.defaultdict(dict)
    for (code, spd), s in tiers.items():
        by[code][spd] = s

    ships = {}
    for code, sd in sorted(by.items()):
        # Binary rule: if Actual has ANY tier for this vessel, the vessel is ACT.
        # TCD is used only as a fallback when Actual has no data for that vessel.
        typ = 'ACT' if 'ACT' in sd.values() else 'TCD'
        ships[code] = {
            'type': typ,
            'act': sum(1 for s in sd.values() if s == 'ACT'),
            'tcd': sum(1 for s in sd.values() if s == 'TCD'),
            'tiers': {('%g' % sp): s for sp, s in sorted(sd.items())}
        }

    # Preserve the existing note (it carries the Port Charges code convention).
    try:
        old_note = json.load(open(OUT, encoding='utf-8')).get('note', '')
    except (OSError, ValueError):
        old_note = ''
    if not old_note:
        old_note = ('数据来源二选一：ACT=该船在 Actual Daily Consumption 有数据'
                    '（缺档才用 TCD 补）；TCD=Actual 完全没有。'
                    '船码以 Port Charges 账单 shipCode 为准。')
    out = {
        'generated': datetime.date.today().isoformat(),
        'note': old_note,
        'ships': ships
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write('\n')

    c = collections.Counter(v['type'] for v in ships.values())
    print('written', OUT)
    print('ships', len(ships), dict(c))


if __name__ == '__main__':
    main()
