#!/usr/bin/env python3
"""
Generate CUL Voyage Report HTML from bi_vessel_departure.csv

- Parse vessel_voyage: [4-char vessel][4-digit voyage][1-char bound]
- Identify each vessel's home terminal (most common first berth terminal for W bound, or S if no W)
- Sum load quantities by bound direction per voyage
- Calculate voyage duration: current voyage home terminal berth -> next voyage start (same terminal)
- Last voyage marked as "Voyage in progress"

Usage:
  python generate_voyage_report.py --csv-path /path/to/bi_vessel_departure.csv --html-output /path/to/voyage_report.html
"""
import pandas as pd
import re
import json
import argparse
import os
from datetime import datetime

LOAD_COLS = ['load_full_20gp', 'load_empty_20gp', 'load_full_40hc', 'load_empty_40hc']
DISCHARGE_COLS = ['discharge_full_20gp', 'discharge_empty_20gp', 'discharge_full_40hc', 'discharge_empty_40hc']


def parse_args():
    p = argparse.ArgumentParser(description='Generate CUL Voyage Report HTML')
    p.add_argument('--csv-path', required=True, help='Path to bi_vessel_departure.csv')
    p.add_argument('--html-output', default='voyage_report.html', help='Output HTML path')
    return p.parse_args()


def parse_vv(vv):
    """Parse vessel_voyage string into (vessel_name, voyage_num, bound)."""
    if pd.isna(vv):
        return None, None, None
    vv = str(vv).strip()
    m = re.match(r'^([A-Z0-9]{4})(\d{4})([A-Z])$', vv)
    if m:
        return m.group(1), m.group(2), m.group(3)
    return None, None, None


def safe_num(v):
    """Convert to float, return 0 if NaN/None."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return 0
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0


def fmt_dt(dt_str):
    """Format datetime string for display."""
    if not dt_str or pd.isna(dt_str):
        return ''
    try:
        dt = datetime.fromisoformat(str(dt_str).replace('T', ' ').split('.')[0])
        return dt.strftime('%Y-%m-%d %H:%M')
    except:
        return str(dt_str)[:16]


def calc_duration_days(start_str, end_str):
    """Calculate duration in days between two ISO datetime strings."""
    if not start_str or not end_str:
        return None
    try:
        start = datetime.fromisoformat(str(start_str).replace('T', ' ').split('.')[0])
        end = datetime.fromisoformat(str(end_str).replace('T', ' ').split('.')[0])
        diff = end - start
        total_hours = diff.total_seconds() / 3600
        days = int(total_hours // 24)
        hours = int(total_hours % 24)
        return f"{days}d {hours}h"
    except:
        return None


def identify_home_terminal(vessel_df):
    """Identify the home terminal for a vessel.
    Use the most common first-berth terminal across W bound voyages.
    If no W bound, try S, then N, then E.
    """
    from collections import Counter
    for bound_pref in ['W', 'S', 'N', 'E']:
        bound_recs = vessel_df[vessel_df['bound'] == bound_pref]
        if len(bound_recs) == 0:
            continue
        first_terminals = []
        for vn, vg in bound_recs.groupby('voyage_num'):
            vg_sorted = vg.sort_values('berth')
            if len(vg_sorted) > 0:
                first_terminals.append(vg_sorted.iloc[0]['terminal'])
        if first_terminals:
            counter = Counter(first_terminals)
            return counter.most_common(1)[0][0], bound_pref
    return None, None


def generate_report(csv_path, html_path):
    print("[1/5] Loading CSV data...")
    df = pd.read_csv(csv_path)
    # Drop placeholder / to-be-nominated vessels (TBN1, TBN2 ...) for consistency
    # with the published CSV (update_vessel_data.py excludes the same prefixes).
    if 'vessel_voyage' in df.columns:
        mask = df['vessel_voyage'].astype(str).str.upper().str.startswith('TBN')
        removed = int(mask.sum())
        if removed:
            df = df[~mask].copy()
            print(f"  Dropped {removed} TBN placeholder records")
    cul = df[df['operator'] == 'CUL'].copy()
    print(f"  CUL records: {len(cul)}")

    print("[2/5] Parsing vessel_voyage...")
    parsed = cul['vessel_voyage'].apply(parse_vv)
    cul['vessel_name'] = parsed.apply(lambda x: x[0])
    cul['voyage_num'] = parsed.apply(lambda x: x[1])
    cul['bound'] = parsed.apply(lambda x: x[2])
    cul = cul.dropna(subset=['vessel_name'])
    print(f"  Parsed successfully: {len(cul)} records, {cul['vessel_name'].nunique()} vessels")

    print("[3/5] Identifying home terminals...")
    vessel_info = {}
    for vn in sorted(cul['vessel_name'].unique()):
        vdf = cul[cul['vessel_name'] == vn]
        home_term, primary_bound = identify_home_terminal(vdf)
        vessel_info[vn] = {'home_terminal': home_term, 'primary_bound': primary_bound}
        print(f"  {vn}: home={home_term}, primary_bound={primary_bound}")

    print("[4/5] Building voyage report data...")
    voyages = []
    for vn in sorted(cul['vessel_name'].unique()):
        vdf = cul[cul['vessel_name'] == vn]
        home_term = vessel_info[vn]['home_terminal']
        primary_bound = vessel_info[vn]['primary_bound']

        voyage_nums = sorted(vdf['voyage_num'].unique(), key=lambda x: int(x))

        voyage_starts = {}
        for vnum in voyage_nums:
            vnum_recs = vdf[(vdf['voyage_num'] == vnum) & (vdf['bound'] == primary_bound)]
            if home_term:
                home_recs = vnum_recs[vnum_recs['terminal'] == home_term]
                if len(home_recs) > 0:
                    home_recs_sorted = home_recs.sort_values('berth')
                    voyage_starts[vnum] = home_recs_sorted.iloc[0]['berth']
                else:
                    if len(vnum_recs) > 0:
                        voyage_starts[vnum] = vnum_recs.sort_values('berth').iloc[0]['berth']
                    else:
                        voyage_starts[vnum] = None
            else:
                voyage_starts[vnum] = None

        for i, vnum in enumerate(voyage_nums):
            vnum_recs = vdf[vdf['voyage_num'] == vnum]

            load_summary = {}
            discharge_summary = {}
            teu_summary = {}
            for bound in ['W', 'E', 'S', 'N']:
                bound_recs = vnum_recs[vnum_recs['bound'] == bound]
                load_total = sum(safe_num(bound_recs[c].sum()) for c in LOAD_COLS)
                discharge_total = sum(safe_num(bound_recs[c].sum()) for c in DISCHARGE_COLS)
                load_teu = (safe_num(bound_recs['load_full_20gp'].sum()) +
                           safe_num(bound_recs['load_empty_20gp'].sum()) +
                           (safe_num(bound_recs['load_full_40hc'].sum()) +
                            safe_num(bound_recs['load_empty_40hc'].sum())) * 2)
                load_summary[bound] = load_total
                discharge_summary[bound] = discharge_total
                teu_summary[bound] = load_teu

            restows_total = safe_num(vnum_recs['restows'].sum())

            start_time = voyage_starts.get(vnum)
            if i + 1 < len(voyage_nums):
                next_vnum = voyage_nums[i + 1]
                end_time = voyage_starts.get(next_vnum)
                is_last = False
            else:
                end_time = None
                is_last = True

            duration = calc_duration_days(start_time, end_time) if end_time else None

            ports = vnum_recs['terminal'].nunique()

            voyages.append({
                'vessel': vn,
                'voyage': vnum,
                'home_terminal': home_term or '',
                'start_time': fmt_dt(start_time),
                'end_time': fmt_dt(end_time) if end_time else ('Voyage in progress' if is_last else ''),
                'duration': duration or ('-' if is_last else ''),
                'is_last': is_last,
                'w_load': int(load_summary.get('W', 0)),
                'e_load': int(load_summary.get('E', 0)),
                's_load': int(load_summary.get('S', 0)),
                'n_load': int(load_summary.get('N', 0)),
                'total_load': int(sum(load_summary.values())),
                'w_load_teu': int(teu_summary.get('W', 0)),
                'e_load_teu': int(teu_summary.get('E', 0)),
                's_load_teu': int(teu_summary.get('S', 0)),
                'n_load_teu': int(teu_summary.get('N', 0)),
                'total_load_teu': int(sum(teu_summary.values())),
                'w_discharge': int(discharge_summary.get('W', 0)),
                'e_discharge': int(discharge_summary.get('E', 0)),
                's_discharge': int(discharge_summary.get('S', 0)),
                'n_discharge': int(discharge_summary.get('N', 0)),
                'total_discharge': int(sum(discharge_summary.values())),
                'restows': int(restows_total),
                'ports': ports,
            })

    print(f"  Total voyages: {len(voyages)}")

    print("[5/5] Generating HTML report...")
    html = generate_html(voyages, vessel_info)
    os.makedirs(os.path.dirname(html_path) or '.', exist_ok=True)
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  HTML saved to: {html_path}")
    print("Done!")


def generate_html(voyages, vessel_info):
    vessels = sorted(set(v['vessel'] for v in voyages))
    voyages_json = json.dumps(voyages, ensure_ascii=False)
    vessel_info_json = json.dumps(vessel_info, ensure_ascii=False)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CUL Voyage Report</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; background: #f0f2f5; color: #333; font-size: 14px; }}
.header {{ background: linear-gradient(135deg, #1a237e, #3949ab); color: white; padding: 16px 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); }}
.header h1 {{ font-size: 22px; margin-bottom: 4px; }}
.header .subtitle {{ font-size: 13px; opacity: 0.85; }}
.container {{ max-width: 1600px; margin: 0 auto; padding: 12px; }}

.filter-bar {{ background: white; border-radius: 8px; padding: 10px 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 12px; }}
.filter-bar label {{ font-size: 12px; color: #666; font-weight: 600; }}
.filter-bar select, .filter-bar input {{ padding: 5px 8px; border: 1px solid #ddd; border-radius: 6px; font-size: 13px; background: #fff; }}
.filter-bar select {{ min-width: 120px; }}
.filter-bar input[type="text"] {{ width: 160px; }}
.btn {{ padding: 5px 12px; border: none; border-radius: 6px; cursor: pointer; font-size: 12px; font-weight: 500; transition: background 0.2s; }}
.btn-blue {{ background: #1a73e8; color: white; }}
.btn-blue:hover {{ background: #1557b0; }}
.btn-gray {{ background: #e8eaed; color: #333; }}
.btn-gray:hover {{ background: #d2d5d9; }}

.summary-cards {{ display: flex; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }}
.summary-card {{ background: white; border-radius: 8px; padding: 12px 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); min-width: 140px; }}
.summary-card .label {{ font-size: 11px; color: #888; text-transform: uppercase; letter-spacing: 0.5px; }}
.summary-card .value {{ font-size: 24px; font-weight: 700; margin-top: 4px; }}
.summary-card .value.blue {{ color: #1a73e8; }}
.summary-card .value.green {{ color: #137333; }}
.summary-card .value.red {{ color: #c5221f; }}
.summary-card .value.purple {{ color: #7b1fa2; }}

.table-wrap {{ background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); overflow: auto; max-height: calc(100vh - 280px); }}
table.data-table {{ width: 100%; border-collapse: collapse; font-size: 12px; white-space: nowrap; }}
table.data-table thead {{ position: sticky; top: 0; z-index: 10; }}
table.data-table th {{ background: #f8f9fa; padding: 8px 10px; text-align: left; font-weight: 600; color: #555; border-bottom: 2px solid #ddd; cursor: pointer; user-select: none; position: relative; }}
table.data-table th:hover {{ background: #e8eaed; }}
table.data-table th.sorted-asc {{ background: #d2e3fc; }}
table.data-table th.sorted-desc {{ background: #d2e3fc; }}
table.data-table th .sort-arrow {{ font-size: 10px; margin-left: 4px; }}
table.data-table td {{ padding: 6px 10px; border-bottom: 1px solid #f0f0f0; }}
table.data-table tr:hover {{ background: #f8f9ff; }}
table.data-table td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
table.data-table td.bold {{ font-weight: 700; color: #1a73e8; }}
table.data-table tr.last-voyage {{ background: #fff9e6; }}
table.data-table tr.last-voyage:hover {{ background: #fff5cc; }}

.th-w {{ color: #1565c0; border-bottom-color: #90caf9; }}
.th-e {{ color: #2e7d32; border-bottom-color: #a5d6a7; }}
.th-s {{ color: #6a1b9a; border-bottom-color: #ce93d8; }}
.th-n {{ color: #e65100; border-bottom-color: #ffcc80; }}
.td-w-load {{ color: #1565c0; }}
.td-e-load {{ color: #2e7d32; }}
.td-s-load {{ color: #6a1b9a; }}
.td-n-load {{ color: #e65100; }}

.group-header th {{ background: #e8eaf6; color: #1a237e; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; }}
.vessel-group td {{ background: #f5f7fa; font-weight: 700; color: #1a237e; font-size: 13px; padding: 6px 10px; }}

.no-data {{ text-align: center; padding: 40px; color: #999; font-size: 16px; }}
.duration-cell {{ font-weight: 600; }}
.duration-cell.long {{ color: #c5221f; }}
.last-badge {{ display: inline-block; background: #ff9800; color: white; font-size: 10px; padding: 1px 6px; border-radius: 10px; margin-left: 4px; }}
</style>
</head>
<body>
<div class="header">
  <h1>CUL Voyage Report</h1>
  <div class="subtitle">Voyage-level summary by vessel & voyage number - Load quantities, voyage duration, port calls</div>
</div>
<div class="container">
  <div class="filter-bar">
    <label>Vessel</label>
    <select id="vesselFilter" onchange="applyFilter()">
      <option value="">All Vessels</option>
    </select>
    <label>Search</label>
    <input type="text" id="searchInput" placeholder="Voyage / Terminal..." oninput="applyFilter()">
    <button class="btn btn-gray" onclick="resetFilter()">Reset</button>
    <span style="flex:1"></span>
    <button class="btn btn-blue" onclick="exportCSV()">Export CSV</button>
  </div>

  <div class="summary-cards" id="summaryCards"></div>

  <div class="table-wrap">
    <table class="data-table" id="dataTable">
      <thead></thead>
      <tbody></tbody>
    </table>
  </div>
</div>

<script>
const ALL_DATA = {voyages_json};
const VESSEL_INFO = {vessel_info_json};
let filtered = [];
let sortKey = null;
let sortDir = 'asc';

const COLS = [
  {{ key: 'vessel', label: 'Vessel', group: 'info' }},
  {{ key: 'voyage', label: 'Voyage', group: 'info' }},
  {{ key: 'home_terminal', label: 'Home Terminal', group: 'info' }},
  {{ key: 'start_time', label: 'Voyage Start', group: 'time' }},
  {{ key: 'end_time', label: 'Voyage End', group: 'time' }},
  {{ key: 'duration', label: 'Duration', group: 'time' }},
  {{ key: 'ports', label: 'Ports', group: 'info', num: true }},
  {{ key: 'w_load', label: 'W Load', group: 'load', cls: 'th-w td-w-load', num: true }},
  {{ key: 'e_load', label: 'E Load', group: 'load', cls: 'th-e td-e-load', num: true }},
  {{ key: 's_load', label: 'S Load', group: 'load', cls: 'th-s td-s-load', num: true }},
  {{ key: 'n_load', label: 'N Load', group: 'load', cls: 'th-n td-n-load', num: true }},
  {{ key: 'total_load', label: 'Total Load', group: 'load', num: true, bold: true }},
  {{ key: 'w_load_teu', label: 'W TEU', group: 'teu', cls: 'th-w td-w-load', num: true }},
  {{ key: 'e_load_teu', label: 'E TEU', group: 'teu', cls: 'th-e td-e-load', num: true }},
  {{ key: 's_load_teu', label: 'S TEU', group: 'teu', cls: 'th-s td-s-load', num: true }},
  {{ key: 'n_load_teu', label: 'N TEU', group: 'teu', cls: 'th-n td-n-load', num: true }},
  {{ key: 'total_load_teu', label: 'Total TEU', group: 'teu', num: true, bold: true }},
  {{ key: 'w_discharge', label: 'W Disch', group: 'disch', cls: 'th-w', num: true }},
  {{ key: 'e_discharge', label: 'E Disch', group: 'disch', cls: 'th-e', num: true }},
  {{ key: 's_discharge', label: 'S Disch', group: 'disch', cls: 'th-s', num: true }},
  {{ key: 'n_discharge', label: 'N Disch', group: 'disch', cls: 'th-n', num: true }},
  {{ key: 'total_discharge', label: 'Total Disch', group: 'disch', num: true, bold: true }},
  {{ key: 'restows', label: 'Restows', group: 'info', num: true }},
];

function init() {{
  const vessels = [...new Set(ALL_DATA.map(v => v.vessel))].sort();
  const sel = document.getElementById('vesselFilter');
  vessels.forEach(v => {{
    const opt = document.createElement('option');
    opt.value = v;
    opt.textContent = v + ' (' + (VESSEL_INFO[v]?.home_terminal || '') + ')';
    sel.appendChild(opt);
  }});
  applyFilter();
}}

function applyFilter() {{
  const vessel = document.getElementById('vesselFilter').value;
  const search = document.getElementById('searchInput').value.toLowerCase();
  filtered = ALL_DATA.filter(v => {{
    if (vessel && v.vessel !== vessel) return false;
    if (search) {{
      const haystack = (v.vessel + v.voyage + v.home_terminal + v.start_time + v.end_time).toLowerCase();
      if (!haystack.includes(search)) return false;
    }}
    return true;
  }});
  if (sortKey) applySort();
  renderTable();
  renderSummary();
}}

function resetFilter() {{
  document.getElementById('vesselFilter').value = '';
  document.getElementById('searchInput').value = '';
  applyFilter();
}}

function toggleSort(key) {{
  if (sortKey === key) {{
    if (sortDir === 'asc') sortDir = 'desc';
    else {{ sortKey = null; sortDir = 'asc'; }}
  }} else {{
    sortKey = key;
    sortDir = 'asc';
  }}
  applySort();
  renderTable();
}}

function applySort() {{
  filtered.sort((a, b) => {{
    let va = a[sortKey], vb = b[sortKey];
    if (a.vessel !== b.vessel) return a.vessel.localeCompare(b.vessel);
    if (sortKey === 'voyage') {{
      va = parseInt(va); vb = parseInt(vb);
      return sortDir === 'asc' ? va - vb : vb - va;
    }}
    const col = COLS.find(c => c.key === sortKey);
    if (col && col.num) {{
      va = parseFloat(va) || 0; vb = parseFloat(vb) || 0;
      return sortDir === 'asc' ? va - vb : vb - va;
    }}
    va = String(va || ''); vb = String(vb || '');
    return sortDir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va);
  }});
}}

function renderTable() {{
  const thead = document.getElementById('dataTable').querySelector('thead');
  const tbody = document.getElementById('dataTable').querySelector('tbody');

  let groupHtml = '<tr class="group-header"><th colspan="7">Voyage Info</th><th colspan="5">Load (Boxes)</th><th colspan="5">Load (TEU)</th><th colspan="5">Discharge (Boxes)</th><th rowspan="2">Restows</th></tr>';
  let colHtml = '<tr>';
  COLS.forEach(c => {{
    let sortCls = '';
    let arrow = '';
    if (sortKey === c.key) {{
      sortCls = sortDir === 'asc' ? ' sorted-asc' : ' sorted-desc';
      arrow = sortDir === 'asc' ? ' \\u25B2' : ' \\u25BC';
    }}
    const cls = c.cls ? c.cls.split(' ')[0] : '';
    colHtml += '<th class="' + cls + sortCls + '" onclick="toggleSort(\\'' + c.key + '\\')">' + c.label + '<span class="sort-arrow">' + arrow + '</span></th>';
  }});
  colHtml += '</tr>';
  thead.innerHTML = groupHtml + colHtml;

  if (!filtered.length) {{
    tbody.innerHTML = '<tr><td colspan="' + (COLS.length + 1) + '" class="no-data">No matching data</td></tr>';
    return;
  }}

  let html = '';
  let lastVessel = '';
  filtered.forEach(v => {{
    if (v.vessel !== lastVessel) {{
      html += '<tr class="vessel-group"><td colspan="' + (COLS.length + 1) + '">' + v.vessel + ' - Home Terminal: ' + v.home_terminal + '</td></tr>';
      lastVessel = v.vessel;
    }}
    let rowCls = v.is_last ? ' class="last-voyage"' : '';
    html += '<tr' + rowCls + '>';
    COLS.forEach(c => {{
      let val = v[c.key];
      let cls = c.num ? 'num' : '';
      if (c.bold) cls += ' bold';
      if (c.cls) {{
        const cellCls = c.cls.split(' ').find(x => x.startsWith('td-'));
        if (cellCls) cls += ' ' + cellCls;
      }}
      if (c.key === 'duration' && val && val !== '-') {{
        const days = parseInt(val);
        if (days > 14) cls += ' duration-cell long';
        else cls += ' duration-cell';
      }}
      if (c.key === 'end_time' && v.is_last) {{
        val = '<span class="last-badge">LAST</span> ' + val;
      }}
      html += '<td class="' + cls + '">' + val + '</td>';
    }});
    html += '</tr>';
  }});
  tbody.innerHTML = html;
}}

function renderSummary() {{
  const total = filtered.length;
  const completed = filtered.filter(v => !v.is_last).length;
  const totalLoad = filtered.reduce((s, v) => s + v.total_load, 0);
  const totalTEU = filtered.reduce((s, v) => s + v.total_load_teu, 0);
  const totalDisch = filtered.reduce((s, v) => s + v.total_discharge, 0);

  document.getElementById('summaryCards').innerHTML =
    '<div class="summary-card"><div class="label">Total Voyages</div><div class="value blue">' + total + '</div></div>' +
    '<div class="summary-card"><div class="label">Completed</div><div class="value green">' + completed + '</div></div>' +
    '<div class="summary-card"><div class="label">In Progress</div><div class="value red">' + (total - completed) + '</div></div>' +
    '<div class="summary-card"><div class="label">Total Load (Boxes)</div><div class="value blue">' + totalLoad.toLocaleString() + '</div></div>' +
    '<div class="summary-card"><div class="label">Total Load (TEU)</div><div class="value purple">' + totalTEU.toLocaleString() + '</div></div>' +
    '<div class="summary-card"><div class="label">Total Discharge (Boxes)</div><div class="value green">' + totalDisch.toLocaleString() + '</div></div>';
}}

function exportCSV() {{
  const headers = COLS.map(c => c.label);
  const rows = [headers.join(',')];
  filtered.forEach(v => {{
    rows.push(COLS.map(c => {{
      let val = v[c.key] ?? '';
      val = String(val).replace(/,/g, ';');
      return val;
    }}).join(','));
  }});
  const csv = rows.join('\\n');
  const blob = new Blob([csv], {{ type: 'text/csv' }});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'cul_voyage_report.csv';
  a.click();
  URL.revokeObjectURL(url);
}}

init();
</script>
</body>
</html>'''


if __name__ == '__main__':
    args = parse_args()
    generate_report(args.csv_path, args.html_output)
