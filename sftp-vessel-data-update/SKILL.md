---
name: sftp-vessel-data-update
description: Automates downloading Vessel Departure Report from SFTP, converting Excel to CSV, pushing to GitHub, and generating CUL Voyage Report HTML. Use when user asks to update vessel data, sync SFTP data, generate voyage report, or set up automated daily data updates.
agent_created: true
---

# SFTP Vessel Data Update Skill

This skill automates the daily workflow of:
1. Downloading the latest `Vessel Departure Report.xlsx` from a company SFTP server
2. Converting the Excel file to a clean CSV
3. Committing and pushing the CSV to a GitHub Pages repository
4. Generating a CUL Voyage Report HTML from the CSV data

## Dependencies

Install before first run:

```bash
pip install paramiko pandas openpyxl
```

## Skill Scripts

### `scripts/update_vessel_data.py`

Downloads Excel from SFTP and converts to CSV.

**Vessel exclusion:** Rows whose `vessel_voyage` starts with any prefix in
`EXCLUDED_VESSEL_PREFIXES` (default `['TBN']`, case-insensitive) are dropped
**before** the CSV is written and pushed. This removes placeholder / to-be-nominated
vessels (TBN1, TBN2, ...) from the published data. `srl_no` is renumbered so it stays
sequential. To drop more placeholder prefixes, edit `EXCLUDED_VESSEL_PREFIXES` at the top
of the script.

**Usage:**

```bash
python scripts/update_vessel_data.py --work-dir /path/to/git/repo [options]
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--work-dir` | current dir | Git repo root directory |
| `--sftp-host` | `10.5.4.2` | SFTP server host |
| `--sftp-port` | `6622` | SFTP server port |
| `--sftp-user` | `leah` | SFTP username |
| `--sftp-pass` | `Fine@B!` | SFTP password |
| `--remote-dir` | `Master Data - Leah` | SFTP remote directory |
| `--remote-file` | `Vessel Departure Report.xlsx` | Remote filename |
| `--csv-output` | `<work-dir>/shipping_data/bi_vessel_departure.csv` | CSV output path |
| `--no-push` | false | Skip git push |

Credentials can also be set via environment variables: `SFTP_HOST`, `SFTP_PORT`, `SFTP_USER`, `SFTP_PASS`, `SFTP_REMOTE_DIR`, `SFTP_REMOTE_FILE`.

**Output:** CSV file at `--csv-output` path.

---

### `scripts/generate_voyage_report.py`

Generates `voyage_report.html` from the CSV for CUL operator vessels.

**Usage:**

```bash
python scripts/generate_voyage_report.py --csv-path /path/to/bi_vessel_departure.csv --html-output /path/to/voyage_report.html
```

**What it does:**
- Filters CSV to `operator == 'CUL'`
- Parses `vessel_voyage` (format: `CCCCNNNNB` where C=4-char vessel, N=4-digit voyage, B=bound direction W/E/S/N)
- Identifies each vessel's home terminal (most common first-berth terminal for primary bound)
- Calculates voyage duration: home terminal berth → next voyage's home terminal berth
- Last voyage marked "Voyage in progress"
- Outputs a self-contained HTML with vessel filter, search, column sort, summary cards, and CSV export

---

## Full Workflow (Daily Automation)

To run the full daily update:

```bash
# Step 1: Download + CSV + Git push
python scripts/update_vessel_data.py --work-dir /path/to/Schedule-Simulation

# Step 2: Generate voyage report
python scripts/generate_voyage_report.py \
  --csv-path /path/to/Schedule-Simulation/shipping_data/bi_vessel_departure.csv \
  --html-output /path/to/Schedule-Simulation/voyage_report.html

# Step 3: Push voyage report
cd /path/to/Schedule-Simulation
git add voyage_report.html
git commit -m "Update voyage report"
git push origin main
```

---

## SFTP Configuration

| Field | Value |
|-------|-------|
| Host | `10.5.4.2` |
| Port | `6622` |
| User | `leah` |
| Password | `Fine@B!` |
| Remote dir | `Master Data - Leah` |
| Remote file | `Vessel Departure Report.xlsx` |

Override any value with command-line arguments.

---

## Expected CSV Columns

The script expects these Excel columns and renames them:

```
TERMINAL → terminal
SVC → svc
OPERATOR → operator
VESSEL / VOYAGE → vessel_voyage
ARRIVED / ANCHORAGE → arrived_anchorage
BERTH → berth
DEPARTURE → departure
WAIT TIME → wait_time
PORT STAY → port_stay
TOTAL MOVES → total_moves
VESSEL MPGH → vessel_mpgh
Discharging Vol. Full 20GP → discharge_full_20gp
Discharging Vol. Full 40HC → discharge_full_40hc
Discharging Vol. Empty 20GP → discharge_empty_20gp
Discharging Vol. Empty 40HC → discharge_empty_40hc
Load Vol. Full 20GP → load_full_20gp
Load Vol. Full 40HC → load_full_40hc
Load Vol. Empty 20GP → load_empty_20gp
Load Vol. Empty 40HC → load_empty_40hc
RESTOWS → restows
Arrival Fuel Oil → arr_fuel_oil
Arrival LSFO → arr_lsfo
Arrival DIESEL OIL → arr_diesel_oil
Arrival LSDO → arr_lsdo
Departure Fuel Oil → dep_fuel_oil
Departure LSFO → dep_lsfo
Departure DIESEL OIL → dep_diesel_oil
Departure LSDO → dep_lsdo
```

---

## Troubleshooting

**`git push` rejected:** Run `git pull --no-rebase origin main` first, then push again.

**`ModuleNotFoundError: No module named 'paramiko'`:** Run `pip install paramiko pandas openpyxl`.

**SFTP connection timeout:** Verify VPN is connected; the SFTP host `10.5.4.2` is an internal IP.
