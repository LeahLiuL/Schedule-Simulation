import csv
from datetime import datetime, timedelta

# Port mapping
rotation_names = [
    ('CNXGG', 'XINGANG (TIANJIN)'),
    ('CNTAO', 'QINGDAO'),
    ('CNSHA', 'SHANGHAI'),
    ('CNNGB', 'NINGBO'),
    ('CNSHK', 'SHEKOU'),
    ('MYPKG', 'PORT KLANG'),
    ('INNSA', 'NHAVA SHEVA'),
    ('PKKHI', 'KARACHI'),
    ('AEKLF', 'KHOR FAKKAN')
]

# Read distances
dist = {}
with open('shipping_data/distances.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        key = (row['from_port'], row['to_port'])
        dist[key] = float(row['distance_nm'])

dist[('CNXGG', 'CNTAO')] = 452
dist[('INNSA', 'PKKHI')] = 560
dist[('PKKHI', 'AEKLF')] = 605

rotation = [r[0] for r in rotation_names]

speed = 16.0
man_in_hours = 3

port_stay_map = {
    'CNXGG': 24, 'CNTAO': 24, 'CNSHA': 24, 'CNNGB': 24, 'CNSHK': 24,
    'MYPKG': 24,
    'INNSA': 36, 'PKKHI': 36,
    'AEKLF': 48
}

start_eta = datetime(2026, 4, 14, 6, 0)

def round_hour(dt):
    if dt.minute >= 30:
        return dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    return dt.replace(minute=0, second=0, microsecond=0)

# Build schedule - NO waiting time
schedule = []
for i, port in enumerate(rotation):
    name = rotation_names[i][1]
    if i == 0:
        eta = round_hour(start_eta)
        etb = round_hour(eta + timedelta(hours=man_in_hours))
        etd = round_hour(etb + timedelta(hours=port_stay_map[port]))
        run_distance = 0
        run_hours = 0
    else:
        run_distance = dist.get((rotation[i-1], port), 0)
        run_hours = run_distance / speed
        eta = round_hour(prev_etd + timedelta(hours=run_hours))
        etb = round_hour(eta + timedelta(hours=man_in_hours))
        etd = round_hour(etb + timedelta(hours=port_stay_map[port]))

    schedule.append({
        'port_code': port,
        'port_name': name,
        'eta': eta,
        'etb': etb,
        'etd': etd,
        'run_distance': run_distance,
        'run_hours': run_hours,
        'port_stay': port_stay_map[port],
        'man_in': man_in_hours,
    })
    prev_etd = etd

total_dist = sum(s['run_distance'] for s in schedule)
total_sea_days = sum(s['run_hours'] for s in schedule) / 24

html = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body { font-family: 'Calibri', 'Arial', sans-serif; font-size: 13px; margin: 30px; background: #fff; }
  h1 { font-size: 18px; margin-bottom: 5px; }
  h2 { font-size: 14px; color: #555; margin-top: 0; font-weight: normal; }
  .info { font-size: 12px; color: #666; margin-bottom: 15px; }
  table { border-collapse: collapse; width: 100%; max-width: 1100px; }
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
</style>
</head>
<body>

<div class="voy-info">TBN (To Be Nominated) &nbsp;|&nbsp; HAMD &nbsp;|&nbsp; Speed: 16.0 kts</div>
<h1>Voyage Schedule (No Waiting Time)</h1>
<h2>Rotation: Tianjin / Qingdao / Shanghai / Ningbo / Shekou / Port Kelang / Nhava Sheva / Karachi / Khor Fakkan</h2>
<p class="info">ETA 1st Port: 14th April 2026 &nbsp;|&nbsp; CN Port Stay: 24h &nbsp;|&nbsp; NHAVA SHEVA / KARACHI: 36h &nbsp;|&nbsp; KHOR FAKKAN: 48h &nbsp;|&nbsp; Man-in: 3h/port</p>

<table>
<thead>
<tr>
  <th>PORT</th>
  <th>VOY.NO</th>
  <th>ETA</th>
  <th>ETB</th>
  <th>ETD</th>
  <th class="num-cell">RUN<br>(nm)</th>
  <th class="num-cell">SEA<br>(hrs)</th>
  <th>PORT STAY<br>(hrs)</th>
  <th class="num-cell">MAN IN<br>(hrs)</th>
  <th class="num-cell">FSP<br>DIST</th>
  <th class="num-cell">SPEED<br>(kts)</th>
</tr>
</thead>
<tbody>
"""

for i, s in enumerate(schedule):
    row_class = ''
    if i == 0: row_class = ' first-port'
    elif i == len(schedule)-1: row_class = ' last-port'

    eta_str = s['eta'].strftime('%Y/%m/%d %H:%M')
    etb_str = s['etb'].strftime('%Y/%m/%d %H:%M')
    etd_str = s['etd'].strftime('%Y/%m/%d %H:%M')
    run_str = f"{s['run_distance']:.0f}" if s['run_distance'] > 0 else '-'
    sea_str = f"{s['run_hours']:.1f}" if s['run_hours'] > 0 else '-'
    cum_dist = sum(schedule[j]['run_distance'] for j in range(i+1))

    html += f"""<tr class="{row_class.strip()}">
  <td class="port-cell">{s['port_name']}</td>
  <td>-</td>
  <td class="date-cell">{eta_str}</td>
  <td class="date-cell">{etb_str}</td>
  <td class="date-cell">{etd_str}</td>
  <td class="num-cell">{run_str}</td>
  <td class="num-cell">{sea_str}</td>
  <td class="num-cell">{s['port_stay']}</td>
  <td class="num-cell">{s['man_in']}</td>
  <td class="num-cell">{cum_dist:.0f}</td>
  <td class="num-cell">{speed}</td>
</tr>
"""

html += f"""</tbody>
</table>

<div class="summary">
  <p><span>Total Distance:</span> {total_dist:.0f} nm &nbsp;|&nbsp;
     <span>Total Sea Days:</span> {total_sea_days:.1f} days &nbsp;|&nbsp;
     <span>1st Port:</span> {schedule[0]['eta'].strftime('%d %b %Y')} &nbsp;|&nbsp;
     <span>Last Port ETD:</span> {schedule[-1]['etd'].strftime('%d %b %Y')}</p>
</div>

</body>
</html>
"""

with open('voyage_schedule_nowait.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("Done! voyage_schedule_nowait.html generated.")
print(f"Total: {total_dist:.0f}nm, {total_sea_days:.1f} sea days")
