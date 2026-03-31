import csv, re
from datetime import datetime, timedelta

rotation_names = [
    ('CNXGG', 'XINGANG (TIANJIN)'),
    ('CNTAO', 'QINGDAO'),
    ('CNSHA', 'SHANGHAI'),
    ('CNNGB', 'NINGBO'),
    ('CNNAS', 'NANSHA'),
    ('CNSHK', 'SHEKOU'),
    ('MYPKG', 'PORT KLANG'),
    ('INNSA', 'NHAVA SHEVA'),
    ('INMUN', 'MUNDRA'),
    ('PKKHI', 'KARACHI'),
    ('AEKLF', 'KHOR FAKKAN')
]

dist = {}
with open('shipping_data/distances.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        key = (row['from_port'], row['to_port'])
        dist[key] = float(row['distance_nm'])

dist[('CNXGG', 'CNTAO')] = 452
dist[('INNSA', 'PKKHI')] = 560
dist[('PKKHI', 'AEKLF')] = 605
dist[('INMUN', 'PKKHI')] = 246

rotation = [r[0] for r in rotation_names]

speed = 16.0
man_in_hours = 3

port_stay_map = {
    'CNXGG': 24, 'CNTAO': 24, 'CNSHA': 24, 'CNNGB': 24,
    'CNNAS': 24, 'CNSHK': 24,
    'MYPKG': 24,
    'INNSA': 36, 'INMUN': 36, 'PKKHI': 36,
    'AEKLF': 48
}

waiting_display = {
    'CNTAO': '72h',
    'CNSHA': 'W1 60h W2 24h W4 48h W5 48h',
    'CNNGB': 'YZT 12h NBCT 48h',
    'CNNAS': '12h',
    'CNSHK': '24h',
    'MYPKG': '10h',
}

def max_waiting_hours(s):
    nums = re.findall(r'(\d+)h', s)
    return max(int(n) for n in nums) if nums else 0

waiting_hours = {p: max_waiting_hours(d) for p, d in waiting_display.items()}
for p in rotation:
    waiting_hours.setdefault(p, 0)

start_eta = datetime(2026, 4, 12, 6, 0)  # Changed to 12th April

def round_hour(dt):
    if dt.minute >= 30:
        return dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    return dt.replace(minute=0, second=0, microsecond=0)

def build_schedule(use_waiting):
    schedule = []
    prev_etd = None
    for i, port in enumerate(rotation):
        wt = waiting_hours.get(port, 0) if use_waiting else 0
        if i == 0:
            eta = round_hour(start_eta)
            etb = round_hour(eta + timedelta(hours=man_in_hours + wt))
            etd = round_hour(etb + timedelta(hours=port_stay_map[port]))
            run_distance, run_hours = 0, 0
        else:
            run_distance = dist.get((rotation[i-1], port), 0)
            run_hours = run_distance / speed
            eta = round_hour(prev_etd + timedelta(hours=run_hours))
            etb = round_hour(eta + timedelta(hours=man_in_hours + wt))
            etd = round_hour(etb + timedelta(hours=port_stay_map[port]))
        schedule.append({
            'port_code': port,
            'port_name': rotation_names[i][1],
            'eta': eta, 'etb': etb, 'etd': etd,
            'run_distance': run_distance,
            'run_hours': run_hours,
            'port_stay': port_stay_map[port],
            'man_in': man_in_hours,
            'waiting_hrs': wt,
        })
        prev_etd = etd
    return schedule

CSS = """
  body { font-family: 'Calibri', 'Arial', sans-serif; font-size: 13px; margin: 30px; background: #fff; }
  h1 { font-size: 18px; margin-bottom: 5px; }
  h2 { font-size: 14px; color: #555; margin-top: 0; font-weight: normal; }
  .info { font-size: 12px; color: #666; margin-bottom: 15px; }
  table { border-collapse: collapse; width: 100%; max-width: 1200px; }
  th { background: #1a5276; color: #fff; padding: 8px 10px; text-align: left; font-size: 12px; font-weight: bold; }
  td { padding: 7px 10px; border-bottom: 1px solid #ddd; font-size: 12px; }
  tr:nth-child(even) { background: #f2f7fb; }
  tr:hover { background: #e8f0fe; }
  .port-cell { font-weight: bold; color: #1a5276; }
  .date-cell { white-space: nowrap; }
  .num-cell { text-align: right; }
  .first-port td { background: #d5e8d4; }
  .last-port td { background: #dae8fc; }
  .voy-info { display: inline-block; background: #1a5276; color: #fff; padding: 6px 14px; border-radius: 4px; font-weight: bold; font-size: 14px; margin-bottom: 10px; }
  .summary { margin-top: 15px; font-size: 12px; color: #333; }
  .summary span { font-weight: bold; }
"""

def gen_html(schedule, title_suffix, show_waiting):
    total_dist = sum(s['run_distance'] for s in schedule)
    total_sea_days = sum(s['run_hours'] for s in schedule) / 24

    wait_col = '<th>WAITING<br>TIME</th>' if show_waiting else ''

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>{CSS}</style>
</head><body>
<div class="voy-info">TBN (To Be Nominated) &nbsp;|&nbsp; HAMD &nbsp;|&nbsp; Speed: {speed} kts</div>
<h1>Voyage Schedule {title_suffix}</h1>
<h2>Rotation: Tianjin / Qingdao / Shanghai / Ningbo / Nansha / Shekou / Port Kelang / Nhava Sheva / Mundra / Karachi / Khor Fakkan</h2>
<p class="info">ETA 1st Port: 12th April 2026 &nbsp;|&nbsp; CN Port Stay: 24h &nbsp;|&nbsp; IN Ports: 36h &nbsp;|&nbsp; KHOR FAKKAN: 48h &nbsp;|&nbsp; Man-in: 3h/port</p>
<table><thead><tr>
  <th>PORT</th><th>VOY.NO</th><th>ETA</th><th>ETB</th><th>ETD</th>
  <th class="num-cell">RUN<br>(nm)</th><th class="num-cell">SEA<br>(hrs)</th>
  <th class="num-cell">PORT STAY<br>(hrs)</th><th class="num-cell">MAN IN<br>(hrs)</th>
  {wait_col}
  <th class="num-cell">FSP DIST</th><th class="num-cell">SPEED<br>(kts)</th>
</tr></thead><tbody>
"""
    for i, s in enumerate(schedule):
        row_class = 'first-port' if i == 0 else ('last-port' if i == len(schedule)-1 else '')
        cum_dist = sum(schedule[j]['run_distance'] for j in range(i+1))
        wt_disp = waiting_display.get(s['port_code'], '-') if show_waiting else ''
        wait_td = f'<td>{wt_disp}</td>' if show_waiting else ''
        run_str = f"{s['run_distance']:.0f}" if s['run_distance'] > 0 else '-'
        sea_str = f"{s['run_hours']:.1f}" if s['run_hours'] > 0 else '-'
        html += f"""<tr class="{row_class}">
  <td class="port-cell">{s['port_name']}</td><td>-</td>
  <td class="date-cell">{s['eta'].strftime('%Y/%m/%d %H:%M')}</td>
  <td class="date-cell">{s['etb'].strftime('%Y/%m/%d %H:%M')}</td>
  <td class="date-cell">{s['etd'].strftime('%Y/%m/%d %H:%M')}</td>
  <td class="num-cell">{run_str}</td><td class="num-cell">{sea_str}</td>
  <td class="num-cell">{s['port_stay']}</td><td class="num-cell">{s['man_in']}</td>
  {wait_td}
  <td class="num-cell">{cum_dist:.0f}</td><td class="num-cell">{speed}</td>
</tr>
"""
    html += f"""</tbody></table>
<div class="summary"><p>
  <span>Total Distance:</span> {total_dist:.0f} nm &nbsp;|&nbsp;
  <span>Total Sea Days:</span> {total_sea_days:.1f} days &nbsp;|&nbsp;
  <span>1st Port ETA:</span> {schedule[0]['eta'].strftime('%d %b %Y')} &nbsp;|&nbsp;
  <span>Last Port ETD:</span> {schedule[-1]['etd'].strftime('%d %b %Y')}
</p></div>
</body></html>
"""
    return html

sched_wait   = build_schedule(use_waiting=True)
sched_nowait = build_schedule(use_waiting=False)

with open('voyage_schedule_v4_wait.html', 'w', encoding='utf-8') as f:
    f.write(gen_html(sched_wait,   '(With Waiting Time)', show_waiting=True))

with open('voyage_schedule_v4_nowait.html', 'w', encoding='utf-8') as f:
    f.write(gen_html(sched_nowait, '(No Waiting Time)',   show_waiting=False))

print("Done! Voyage Schedule v4 Generated")
print(f"\nWith waiting  - Last ETD: {sched_wait[-1]['etd'].strftime('%d %b %Y %H:%M')}")
print(f"No  waiting   - Last ETD: {sched_nowait[-1]['etd'].strftime('%d %b %Y %H:%M')}")

print("\n=== CALCULATION LOGIC ===")
print(f"1. Start ETA: {start_eta.strftime('%d %b %Y %H:%M')}")
print(f"2. Speed: {speed} kts, Man-in: {man_in_hours}h/port")
print(f"\n3. Each port calculation:")
print(f"   - First port: ETB = ETA + Man-in + Waiting, ETD = ETB + Port Stay")
print(f"   - Other ports: ETA = Prev_ETD + (distance / speed)")
print(f"                 ETB = ETA + Man-in + Waiting, ETD = ETB + Port Stay")
print(f"4. All times rounded to nearest hour (>=30 min rounds up)")

print("\n=== KEY VALUES ===")
for p in rotation:
    ps = port_stay_map[p]
    wt = waiting_hours.get(p, 0)
    wt_disp = waiting_display.get(p, '-')
    print(f"   {p:6s} - PortStay:{ps}h, Waiting:{wt_disp} ({wt}h)")

print("\n=== DISTANCES ===")
for i in range(1, len(rotation)):
    d = dist.get((rotation[i-1], rotation[i]), 'MISSING')
    sea_hrs = d / speed
    print(f"   {rotation[i-1]:6s} -> {rotation[i]:6s}: {d:7.1f}nm = {sea_hrs:6.2f}hrs")
